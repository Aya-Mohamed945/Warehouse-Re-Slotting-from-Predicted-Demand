"""The single validator used by every module and by the QA suite."""
from .warehouse import manhattan
from .constraints import static_slot_ok, incompatible_aisle_pairs


def validate_layout(products, layout, slots, pair_constraints, require_complete=True):
    """Return a structured report (dict). `layout`: product id -> slot id.
    Pair constraints are checked as HARD constraints; every violation is listed.
    `valid` is True only if every check passes."""
    slots_by_id = {s.slot_id: s for s in slots}
    pby = {str(p["id"]): p for p in products}
    layout = {str(k): v for k, v in layout.items()}

    missing = sorted(set(pby) - set(layout))
    extra = sorted(set(layout) - set(pby))
    invalid_slots = sorted(pid for pid, sid in layout.items() if sid not in slots_by_id)

    seen, duplicate_slots = {}, {}
    for pid, sid in layout.items():
        seen.setdefault(sid, []).append(pid)
    for sid, pids in seen.items():
        if len(pids) > 1:
            duplicate_slots[sid] = sorted(pids)

    capacity_viol, heavy_viol = [], []
    for pid, sid in layout.items():
        if pid not in pby or sid not in slots_by_id:
            continue
        p, s = pby[pid], slots_by_id[sid]
        if p["required_capacity"] > s.capacity:
            capacity_viol.append(pid)
        if p["heavy"] and s.level != "low":
            heavy_viol.append(pid)

    good = {k: v for k, v in layout.items() if k in pby and v in slots_by_id}
    aisle_viol = incompatible_aisle_pairs(good, pby, slots_by_id)

    pair_viol, excess, pairs_unplaced = [], 0, 0
    for a, b, dmax, *_ in pair_constraints:
        a, b = str(a), str(b)
        if a not in good or b not in good:
            pairs_unplaced += 1
            continue
        d = manhattan(slots_by_id[good[a]].pos, slots_by_id[good[b]].pos)
        if d > dmax:
            pair_viol.append((a, b, d, dmax))
            excess += d - dmax

    no_violations = (not extra and not invalid_slots and not duplicate_slots
                     and not capacity_viol and not heavy_viol and not aisle_viol
                     and not pair_viol)
    valid = bool(no_violations and (not require_complete or (not missing and pairs_unplaced == 0)))
    return {
        "total_products": len(pby),
        "assigned_products": len(good),
        "missing_products": missing,
        "unknown_products": extra,
        "invalid_slot_ids": invalid_slots,
        "duplicate_slots": duplicate_slots,
        "capacity_violations": capacity_viol,
        "heavy_shelf_violations": heavy_viol,
        "incompatible_aisle_violations": aisle_viol,
        "pair_violations": pair_viol,
        "pair_constraints_checked": len(pair_constraints) - pairs_unplaced,
        "total_excess_distance": excess,
        "valid": valid,
    }


def hard_basic_ok(report):
    """Slot-level hard rules only (unique, capacity, heavy, complete) - what every layout
    builder must guarantee irrespective of the pair/aisle constraints."""
    return (not report["missing_products"] and not report["unknown_products"]
            and not report["invalid_slot_ids"] and not report["duplicate_slots"]
            and not report["capacity_violations"] and not report["heavy_shelf_violations"])


def report_summary(report):
    r = report
    return {
        "total_products": r["total_products"], "assigned_products": r["assigned_products"],
        "missing": len(r["missing_products"]), "duplicate_slots": len(r["duplicate_slots"]),
        "capacity_violations": len(r["capacity_violations"]),
        "heavy_shelf_violations": len(r["heavy_shelf_violations"]),
        "incompatible_aisle_pairs": len(r["incompatible_aisle_violations"]),
        "pair_violations": len(r["pair_violations"]),
        "total_excess_distance": r["total_excess_distance"], "valid": r["valid"],
    }
