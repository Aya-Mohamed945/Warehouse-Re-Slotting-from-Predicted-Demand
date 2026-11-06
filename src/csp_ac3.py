"""Genuine AC-3 over the binary constraint graph of the warehouse CSP.

Constraint graph (arcs are directed (x, y) = "revise D(x) against D(y)"):
  * co-purchase arc  x--y : value s in D(x) is supported iff some t in D(y) has
                            manhattan(s, t) <= max_distance(x, y)
  * category arc     x--y (incompatible categories): s in D(x) is supported iff some t in D(y)
                            lies in a different aisle than s
The alldifferent (one product per slot) constraint is NOT turned into n^2 binary arcs; it is
enforced by forward checking (value removal on assignment). This is a documented design choice.

Arc queue is initialised with every arc (root call) or with arcs into the variables whose
domains just changed (incremental call). When D(x) shrinks, arcs (z, x) for all neighbours
z != y are re-queued; an empty domain => failure. Revisions / checks are counted."""
from collections import deque
from .csp_model import bits, popcount


def build_arcs(model):
    """target var x -> list of (z, kind, d): arcs (z, x) to re-queue when D(x) changes."""
    nbrs = [[] for _ in range(model.n)]
    for i in range(model.n):
        for j, d in model.pair_nbrs[i].items():
            nbrs[i].append((j, "pair", d))
        for j in model.cat_nbrs[i]:
            nbrs[i].append((j, "cat", None))
    return nbrs


def _revise(model, dom, x, y, kind, d, st):
    """Remove from D(x) values with no support in D(y). Returns (changed, new_mask)."""
    dy, old = dom[y], dom[x]
    st.ac3_revisions += 1
    if kind == "pair":
        support = 0
        ball = model.ball[d]
        for t in bits(dy):
            support |= ball[t]
        st.ac3_checks += popcount(dy)
        new = old & support
    else:
        allowed = 0
        for k, am in model.aisle_mask.items():
            st.ac3_checks += 1
            if dy & ~am:                       # y has a value outside aisle k
                allowed |= am
        new = old & allowed
    return new != old, new


def ac3_propagate(model, dom, nbrs, changed_vars, trail, st, assign):
    """Run AC-3. `changed_vars=None` -> full initial queue. Mutates `dom` and appends
    (index, old_mask) to `trail` so the caller can undo. Returns False if a domain empties."""
    queue, queued = deque(), set()

    def push(z, x, kind, d):
        if (z, x) not in queued:
            queued.add((z, x))
            queue.append((z, x, kind, d))

    if changed_vars is None:
        for x in range(model.n):
            for z, kind, d in nbrs[x]:
                push(z, x, kind, d)
    else:
        for x in changed_vars:
            for z, kind, d in nbrs[x]:
                push(z, x, kind, d)
    while queue:
        x, y, kind, d = queue.popleft()
        queued.discard((x, y))
        changed, new = _revise(model, dom, x, y, kind, d, st)
        if changed:
            trail.append((x, dom[x]))
            st.reductions += popcount(dom[x]) - popcount(new)
            st.ac3_domain_changes += 1
            dom[x] = new
            if new == 0:
                return False
            for z, k2, d2 in nbrs[x]:
                if z != y:
                    push(z, x, k2, d2)
    return True


def solve_fc_ac3(model, max_nodes=10**8, max_seconds=30.0):
    from .csp_forward_checking import solve_fc
    return solve_fc(model, max_nodes, max_seconds, use_ac3=True)
