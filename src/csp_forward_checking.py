"""Backtracking + incremental Forward Checking with MRV (+ degree tie-break).

Domains are bit masks, updated incrementally on assignment and restored from a trail on
backtrack. `solve_fc(..., use_ac3=True)` additionally runs AC-3 after each FC step
(BT+FC+AC-3, see csp_ac3.py)."""
import sys
from .csp_model import CSPModel, Stats, bits, popcount

sys.setrecursionlimit(5000)


def forward_check(model, dom, unassigned, var, s, trail, st, changed):
    """Assign var=s and prune all unassigned domains incrementally.
    Returns False on a domain wipe-out. Records (index, old_mask) in trail."""
    bit = 1 << s
    notbit = ~bit
    amask = ~model.aisle_mask[model.aisle[s]]
    pn, cn = model.pair_nbrs[var], model.cat_nbrs[var]
    catset = None
    for j in unassigned:
        if j == var:
            continue
        old = dom[j]
        new = old & notbit                                   # alldifferent
        d = pn.get(j)
        if d is not None:
            new &= model.ball[d][s]                          # co-purchase distance
            st.checks += 1
        if j in model.cat_set[var]:
            new &= amask                                     # incompatible aisle
            st.checks += 1
        st.checks += 1
        if new != old:
            trail.append((j, old))
            dom[j] = new
            st.reductions += popcount(old) - popcount(new)
            changed.append(j)
            if new == 0:
                return False
    return True


def hall_ok(model, dom, unassigned, st):
    """Global pigeonhole pruning (beyond plain FC): the still-unassigned products that share the
    same static domain (e.g. all heavy products -> low shelves) need at least that many distinct
    slots in the UNION of their current domains. Fails early when ordinary products have used up
    the low shelves that heavy products still need."""
    for group in model.hall_groups:
        members = [j for j in group if j in unassigned]
        if len(members) > 1:
            union = 0
            for j in members:
                union |= dom[j]
            st.checks += 1
            if popcount(union) < len(members):
                return False
    return True


def solve_fc(model: CSPModel, max_nodes=10**8, max_seconds=30.0, use_ac3=False):
    if not hasattr(model, "cat_set"):
        model.cat_set = [set(x) for x in model.cat_nbrs]
    if not hasattr(model, "hall_groups"):
        groups = {}
        for i, m in enumerate(model.static_dom):
            if m != model.full:
                groups.setdefault(m, []).append(i)
        model.hall_groups = list(groups.values())
    if use_ac3:
        from .csp_ac3 import ac3_propagate, build_arcs
        arcs_by_target = build_arcs(model)
    st = Stats(max_nodes, max_seconds)
    n = model.n
    dom = list(model.static_dom)
    assign = [-1] * n
    unassigned = set(range(n))
    if any(d == 0 for d in dom):
        return st.result(model, assign, False)

    if use_ac3:
        trail0 = []
        if not ac3_propagate(model, dom, arcs_by_target, None, trail0, st, assign):
            return st.result(model, assign, False)

    def rec():
        st.nodes += 1
        if not unassigned:
            return True
        if st.hit_limit():
            return False
        var = min(unassigned, key=lambda j: (popcount(dom[j]), -model.degree[j], j))   # MRV, degree tie-break
        cand = dom[var]
        unassigned.discard(var)
        for s in bits(cand):
            if st.limit:
                break
            trail, changed = [], []
            old_var = dom[var]
            assign[var] = s
            ok = forward_check(model, dom, unassigned, var, s, trail, st, changed)
            if ok:
                ok = hall_ok(model, dom, unassigned, st)
            if ok and use_ac3:
                dom[var] = 1 << s
                trail.append((var, old_var))
                ok = ac3_propagate(model, dom, arcs_by_target, changed, trail, st, assign)
            if ok and rec():
                return True
            for j, old in reversed(trail):
                dom[j] = old
            assign[var] = -1
            st.backtracks += 1
        unassigned.add(var)
        return False

    solved = rec()
    return st.result(model, assign, solved)
