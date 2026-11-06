"""Greedy Best-First, bounded Uniform-Cost Search and an A* variant over swap sequences.

State  : a complete layout (list of slot ids indexed like `products`).
Action : swap the slots of two products.  Eligible swaps: one product from the TOP_K highest-
         demand products, the partner currently sitting in one of the NEAR_SLOTS slots closest
         to the Depot (or itself a top-K product).
Cost   : 1 per swap.  Depth bound: MAX_DEPTH swaps.  Budget: max_expansions / max_seconds.
Hard   : every generated child is checked (unique slot is inherent to a swap, capacity, heavy->low,
         incompatible-aisle conflicts must not increase); rejected children are never generated.
Goal   : J(state) <= target  (default target = 90 % of the initial objective) or depth == MAX_DEPTH.
Final  : best-objective state generated within the budget (ties -> fewer swaps).
Duplicate states are pruned with a layout signature (tuple of slot ids)."""
import heapq
import itertools
import time
from .optimization import Objective

TOP_K, NEAR_SLOTS, MAX_DEPTH = 30, 40, 6
TARGET_FRACTION = 0.90


def eligible_swaps(obj: Objective, st, near_slots):
    top = range(min(TOP_K, obj.n))
    pairs = set()
    for a in top:
        for b in range(obj.n):
            if b != a and (b < TOP_K or st[b] in near_slots):
                pairs.add((min(a, b), max(a, b)))
    return sorted(pairs)


def max_single_swap_gain(obj, st, counts, near_slots):
    best = 0.0
    for i, j in eligible_swaps(obj, st, near_slots):
        if obj.swap_ok(st, i, j, counts):
            best = max(best, -obj.swap_delta(st, i, j)[0])
    return best


def _search(obj: Objective, start_layout, mode, max_expansions=300, max_seconds=120.0,
            target_fraction=TARGET_FRACTION, max_depth=MAX_DEPTH):
    t0 = time.perf_counter()
    st0 = obj.state_from_layout(start_layout)
    counts0 = obj.aisle_counts(st0)
    near = {s.slot_id for s in sorted(obj.slots, key=lambda s: (obj.d0[s.slot_id], s.row, s.col))[:NEAR_SLOTS]}
    J0 = obj.total(st0)
    target = target_fraction * J0
    delta = max_single_swap_gain(obj, st0, counts0, near) if mode == "astar" else None

    def h_astar(J):
        if J <= target or not delta:
            return 0.0
        return (J - target) / delta          # estimated number of remaining (best-case) swaps

    def priority(g, J):
        if mode == "greedy":
            return (J, g)                    # heuristic only
        if mode == "ucs":
            return (g, J)                    # accumulated cost only (J = tie-break)
        return (g + h_astar(J), J)           # f = g + h

    counter = itertools.count()
    root = {"st": st0, "counts": counts0, "g": 0, "J": J0, "swaps": []}
    heap = [(priority(0, J0), next(counter), root)]
    best_g = {tuple(st0): 0}
    best_node = root
    expanded = generated = 0
    reached = None
    stop = "frontier exhausted"
    while heap:
        if expanded >= max_expansions:
            stop = "expansion budget reached"
            break
        if time.perf_counter() - t0 >= max_seconds:
            stop = "time budget reached"
            break
        _, _, node = heapq.heappop(heap)
        if node["g"] > best_g.get(tuple(node["st"]), 1e9):
            continue
        if node["J"] <= target:
            reached = node
            stop = "goal reached"
            break
        if node["g"] >= max_depth:
            continue
        expanded += 1
        st, counts = node["st"], node["counts"]
        for i, j in eligible_swaps(obj, st, near):
            if not obj.swap_ok(st, i, j, counts):
                continue
            dJ, _, _ = obj.swap_delta(st, i, j)
            child_st = list(st)
            child_st[i], child_st[j] = child_st[j], child_st[i]
            sig = tuple(child_st)
            g = node["g"] + 1
            if best_g.get(sig, 1e9) <= g:
                continue
            best_g[sig] = g
            child_counts = {k: list(v) for k, v in counts.items()}
            obj.apply_swap(list(st), child_counts, i, j)
            child = {"st": child_st, "counts": child_counts, "g": g, "J": node["J"] + dJ,
                     "swaps": node["swaps"] + [(obj.ids[i], obj.ids[j])]}
            generated += 1
            if (child["J"], child["g"]) < (best_node["J"] - 1e-12, best_node["g"]) or \
               (abs(child["J"] - best_node["J"]) <= 1e-12 and child["g"] < best_node["g"]):
                best_node = child
            heapq.heappush(heap, (priority(g, child["J"]), next(counter), child))
    final = reached or best_node
    fst = final["st"]
    e0, c0 = obj.excess(st0)
    e1, c1 = obj.excess(fst)
    return obj.layout_from_state(fst), {
        "initial_objective": round(J0, 4), "final_objective": round(obj.total(fst), 4),
        "target_objective": round(target, 4),
        "initial_wwd": round(obj.wwd(st0), 4), "final_wwd": round(obj.wwd(fst), 4),
        "initial_pair_violations": c0, "final_pair_violations": c1,
        "initial_excess": e0, "final_excess": e1,
        "swaps": final["g"], "swap_list": final["swaps"],
        "expanded_nodes": expanded, "generated_nodes": generated,
        "seconds": round(time.perf_counter() - t0, 3),
        "target_reached": bool(obj.total(fst) <= target + 1e-12),
        "stop_reason": stop,
        "heuristic_delta": None if delta is None else round(delta, 5),
    }


def greedy_best_first(obj, start_layout, **kw):
    return _search(obj, start_layout, "greedy", **kw)


def bounded_ucs(obj, start_layout, **kw):
    return _search(obj, start_layout, "ucs", **kw)


def astar_variant(obj, start_layout, **kw):
    """A* with h = (J - target) / (best single-swap gain at the root). NOT admissible in general
    (a later swap may gain more than the root's best), so optimality is NOT claimed."""
    return _search(obj, start_layout, "astar", **kw)
