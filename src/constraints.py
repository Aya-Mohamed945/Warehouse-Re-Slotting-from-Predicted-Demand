"""Centralised warehouse rules + indexed co-purchase constraints."""
from itertools import combinations
from .warehouse import manhattan

# Simulated business rules (NOT derived from the UCI data). Unordered => symmetric.
INCOMPATIBLE_CATEGORIES = {
    frozenset(("cleaning", "food")),
    frozenset(("cleaning", "fragile")),
}


def categories_incompatible(category_a, category_b):
    """True iff the two categories must not share an aisle. Symmetric; same category -> False."""
    return frozenset((category_a, category_b)) in INCOMPATIBLE_CATEGORIES


def build_pair_index(pair_constraints):
    """product id -> list[(neighbour id, max_distance)].  Accepts 3- or 4-tuples."""
    index = {}
    for a, b, d, *_ in pair_constraints:
        index.setdefault(str(a), []).append((str(b), d))
        index.setdefault(str(b), []).append((str(a), d))
    return index


def static_slot_ok(product, slot):
    """Unary constraints: capacity and heavy -> low shelf."""
    if product["required_capacity"] > slot.capacity:
        return False
    if product["heavy"] and slot.level != "low":
        return False
    return True


def is_valid_slot(product, slot, layout, slots_by_id, products_by_id, pair_index):
    """Check one candidate placement against everything already in `layout`
    (pid -> slot_id). Uses the pair index (no scan of all pairs) and per-aisle checks."""
    if not static_slot_ok(product, slot):
        return False
    for oid, osid in layout.items():
        if osid == slot.slot_id:
            return False
        os_ = slots_by_id[osid]
        if os_.aisle == slot.aisle and categories_incompatible(
                product["category"], products_by_id[oid]["category"]):
            return False
    for oid, dmax in pair_index.get(str(product["id"]), ()):
        if oid in layout:
            os_ = slots_by_id[layout[oid]]
            if manhattan(slot.pos, os_.pos) > dmax:
                return False
    return True


def aisle_capacity_certificate(products, slots):
    """Exact test of the category-aisle rule ALONE (necessary condition for any full layout).

    Every aisle is either 'A-type' (holds only cleaning+stationery) or 'B-type'
    (holds only food+fragile+stationery); an aisle containing a cleaning item cannot contain
    food/fragile. We enumerate which aisles are A-type and check that cleaning fits in the A
    aisles and food+fragile fits in the B aisles. If no assignment works the CSP is infeasible.
    Returns dict(feasible, detail). This is a counting argument, NOT AC-3."""
    aisle_sizes = {}
    for s in slots:
        aisle_sizes[s.aisle] = aisle_sizes.get(s.aisle, 0) + 1
    n_clean = sum(p["category"] == "cleaning" for p in products)
    n_fb = sum(p["category"] in ("food", "fragile") for p in products)
    aisles = sorted(aisle_sizes)
    best = None
    for mask in range(1 << len(aisles)):
        a_cap = sum(aisle_sizes[a] for i, a in enumerate(aisles) if mask >> i & 1)
        b_cap = sum(aisle_sizes[a] for i, a in enumerate(aisles) if not mask >> i & 1)
        if n_clean <= a_cap and n_fb <= b_cap:
            return {"feasible": True, "detail": f"cleaning={n_clean}<=A-capacity {a_cap}, "
                    f"food+fragile={n_fb}<=B-capacity {b_cap}"}
        slack = (a_cap - n_clean, b_cap - n_fb)
        if best is None or min(slack) > min(best):
            best = slack
    return {"feasible": False,
            "detail": f"{n_clean} cleaning products need whole aisles free of food/fragile, "
                      f"{n_fb} food+fragile products need the remaining aisles; no split of "
                      f"{len(aisles)} aisles ({sorted(aisle_sizes.values())} slots) holds both "
                      f"(best slack A/B = {best})"}


def incompatible_aisle_pairs(layout, products_by_id, slots_by_id):
    """List of (pid_a, pid_b, aisle) for every incompatible product pair sharing an aisle."""
    by_aisle = {}
    for pid, sid in layout.items():
        by_aisle.setdefault(slots_by_id[sid].aisle, []).append(pid)
    out = []
    for aisle, pids in by_aisle.items():
        for a, b in combinations(sorted(pids), 2):
            if categories_incompatible(products_by_id[a]["category"], products_by_id[b]["category"]):
                out.append((a, b, aisle))
    return out
