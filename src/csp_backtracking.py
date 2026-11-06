"""Plain chronological backtracking: static variable order (demand order), values tried
Depot-nearest first, every candidate checked only against already-assigned variables
(using the pair index, so no scan of all pair constraints)."""
import sys
from .csp_model import CSPModel, Stats, bits
from .constraints import categories_incompatible

sys.setrecursionlimit(5000)


def solve_bt(model: CSPModel, max_nodes=10**8, max_seconds=30.0):
    st = Stats(max_nodes, max_seconds)
    n = model.n
    assign = [-1] * n
    used = 0
    aisle_cats = {k: {} for k in model.aisles}      # aisle -> category -> count
    cats = [p["category"] for p in model.products]
    ball = model.ball

    def consistent(i, s):
        k = model.aisle[s]
        for c, cnt in aisle_cats[k].items():
            st.checks += 1
            if cnt and categories_incompatible(cats[i], c):
                return False
        for j, d in model.pair_nbrs[i].items():
            if assign[j] >= 0:
                st.checks += 1
                if not (ball[d][s] >> assign[j]) & 1:
                    return False
        return True

    def rec(i):
        nonlocal used
        st.nodes += 1
        if i == n:
            return True
        if st.hit_limit():
            return False
        for s in bits(model.static_dom[i] & ~used):
            if st.limit:
                return False
            if not consistent(i, s):
                continue
            assign[i] = s
            used |= 1 << s
            k = model.aisle[s]
            aisle_cats[k][cats[i]] = aisle_cats[k].get(cats[i], 0) + 1
            if rec(i + 1):
                return True
            aisle_cats[k][cats[i]] -= 1
            used &= ~(1 << s)
            assign[i] = -1
            st.backtracks += 1
        return False

    solved = rec(0)
    return st.result(model, assign, solved)
