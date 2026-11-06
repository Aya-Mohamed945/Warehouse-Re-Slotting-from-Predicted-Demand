"""Layout construction, the documented objective, and swap-based optimisation.

OBJECTIVE (used by Search and by the optimiser; it never touches test invoices):
    J(layout) = WWD(layout) + LAMBDA * total_pair_excess(layout)
  WWD  = sum_i demand_i * manhattan(slot_i, Depot) / sum_i demand_i     (predicted next-week demand)
  excess = sum over co-purchase pairs of max(0, manhattan(a, b) - max_distance)
  LAMBDA = 0.04  (the original notebook used 0.2 per excess unit on a per-invoice distance scale;
                  an invoice has ~4.8 lines, so 0.2/4.8 ~= 0.04 on the per-product WWD scale).
Pair-distance rules are SOFT here (reported separately). HARD for every swap: unique slot,
capacity, heavy->low shelf, and the number of incompatible-category/same-aisle pairs must not
increase (a full 120-product layout cannot satisfy that rule at all - see constraints.py)."""
import math
import random
import time
from .warehouse import manhattan, DEPOT
from .constraints import categories_incompatible, static_slot_ok

LAMBDA = 0.04


# ----------------------------------------------------------------------------- construction
def build_demand_layout(products, slots, key):
    """Highest `key` nearest the Depot; heavy products first onto low shelves (capacity-safe)."""
    ordered = sorted(slots, key=lambda s: (manhattan(s.pos, DEPOT), s.row, s.col))
    heavy = sorted([p for p in products if p["heavy"]], key=lambda p: p[key], reverse=True)
    normal = sorted([p for p in products if not p["heavy"]], key=lambda p: p[key], reverse=True)
    free, layout = list(ordered), {}
    for p in heavy + normal:
        for s in free:
            if static_slot_ok(p, s):
                layout[p["id"]] = s.slot_id
                free.remove(s)
                break
        else:
            raise ValueError(f"no feasible slot for {p['id']}")
    return layout


def build_random_layout(products, slots, seed=42):
    rng = random.Random(seed)
    heavy = [p for p in products if p["heavy"]]
    normal = [p for p in products if not p["heavy"]]
    rng.shuffle(heavy)
    rng.shuffle(normal)
    free = list(slots)
    rng.shuffle(free)
    layout = {}
    for p in heavy + normal:
        for s in free:
            if static_slot_ok(p, s):
                layout[p["id"]] = s.slot_id
                free.remove(s)
                break
        else:
            raise ValueError(f"no feasible slot for {p['id']}")
    return layout


# ----------------------------------------------------------------------------- objective
class Objective:
    """Pre-indexed objective with O(degree) incremental swap evaluation."""

    def __init__(self, products, slots, pair_constraints, lam=LAMBDA):
        self.products, self.slots, self.lam = products, slots, lam
        self.ids = [p["id"] for p in products]
        self.idx = {pid: i for i, pid in enumerate(self.ids)}
        self.n = len(products)
        self.w = [p["demand"] for p in products]
        self.W = sum(self.w)
        self.d0 = {s.slot_id: manhattan(s.pos, DEPOT) for s in slots}
        self.pos = {s.slot_id: s.pos for s in slots}
        self.aisle = {s.slot_id: s.aisle for s in slots}
        self.level = {s.slot_id: s.level for s in slots}
        self.cap = {s.slot_id: s.capacity for s in slots}
        self.cats = sorted({p["category"] for p in products})
        self.cat_of = [self.cats.index(p["category"]) for p in products]
        self.incomp = [[categories_incompatible(a, b) for b in self.cats] for a in self.cats]
        self.pairs = [[] for _ in range(self.n)]       # i -> [(j, dmax)]
        self.pair_list = []
        for a, b, d, *_ in pair_constraints:
            if a in self.idx and b in self.idx:
                i, j = self.idx[a], self.idx[b]
                self.pairs[i].append((j, d))
                self.pairs[j].append((i, d))
                self.pair_list.append((i, j, d))
        self.checks = 0

    # state = list[slot_id] indexed like products
    def state_from_layout(self, layout):
        return [layout[pid] for pid in self.ids]

    def layout_from_state(self, state):
        return {pid: state[i] for i, pid in enumerate(self.ids)}

    def wwd(self, st):
        return sum(w * self.d0[s] for w, s in zip(self.w, st)) / self.W

    def _dist(self, sa, sb):
        pa, pb = self.pos[sa], self.pos[sb]
        return abs(pa[0] - pb[0]) + abs(pa[1] - pb[1])

    def excess(self, st):
        e = c = 0
        for i, j, d in self.pair_list:
            x = self._dist(st[i], st[j]) - d
            if x > 0:
                e += x
                c += 1
        return e, c

    def aisle_counts(self, st):
        counts = {k: [0] * len(self.cats) for k in set(self.aisle.values())}
        for i, s in enumerate(st):
            counts[self.aisle[s]][self.cat_of[i]] += 1
        return counts

    def _conf_row(self, row):
        t = 0
        for a in range(len(row)):
            for b in range(a + 1, len(row)):
                if self.incomp[a][b]:
                    t += row[a] * row[b]
        return t

    def aisle_conflicts(self, st):
        return sum(self._conf_row(r) for r in self.aisle_counts(st).values())

    def total(self, st):
        e, c = self.excess(st)
        return self.wwd(st) + self.lam * e

    # ---- incremental swap -----------------------------------------------------------------
    def swap_ok(self, st, i, j, counts=None):
        """Hard-rule check for swapping the slots of products i and j."""
        si, sj = st[i], st[j]
        pi, pj = self.products[i], self.products[j]
        self.checks += 1
        if pi["required_capacity"] > self.cap[sj] or pj["required_capacity"] > self.cap[si]:
            return False
        if (pi["heavy"] and self.level[sj] != "low") or (pj["heavy"] and self.level[si] != "low"):
            return False
        if counts is not None:
            ki, kj = self.aisle[si], self.aisle[sj]
            if ki != kj:
                ci, cj = self.cat_of[i], self.cat_of[j]
                ri, rj = list(counts[ki]), list(counts[kj])
                before = self._conf_row(ri) + self._conf_row(rj)
                ri[ci] -= 1; ri[cj] += 1
                rj[cj] -= 1; rj[ci] += 1
                if self._conf_row(ri) + self._conf_row(rj) > before:
                    return False
        return True

    def swap_delta(self, st, i, j):
        """Return (delta_J, delta_WWD, delta_excess) for swapping slots of i and j."""
        si, sj = st[i], st[j]
        dw = (self.w[i] - self.w[j]) * (self.d0[sj] - self.d0[si]) / self.W
        de = 0
        for a, other_slot_of in ((i, j), (j, i)):
            sa_old = st[a]
            sa_new = st[other_slot_of]
            for b, d in self.pairs[a]:
                if b == other_slot_of:
                    if a == j:             # pair (i,j) counted once, via i
                        continue
                    old = max(0, self._dist(si, sj) - d)
                    new = old               # distance between the two swapped products unchanged
                    continue
                sb = st[b]
                old = max(0, self._dist(sa_old, sb) - d)
                new = max(0, self._dist(sa_new, sb) - d)
                de += new - old
        return dw + self.lam * de, dw, de

    def apply_swap(self, st, counts, i, j):
        si, sj = st[i], st[j]
        ki, kj = self.aisle[si], self.aisle[sj]
        if ki != kj:
            ci, cj = self.cat_of[i], self.cat_of[j]
            counts[ki][ci] -= 1; counts[ki][cj] += 1
            counts[kj][cj] -= 1; counts[kj][ci] += 1
        st[i], st[j] = sj, si


# ----------------------------------------------------------------------------- optimiser
def simulated_annealing(start_layout, obj: Objective, iterations=30000, seed=42,
                        t_start=0.3, t_end=0.002):
    """Swap-based simulated annealing on J. Hard rules are checked on every candidate; an
    infeasible swap is rejected (never accepted). Returns (best_layout, info)."""
    rng = random.Random(seed)
    st = obj.state_from_layout(start_layout)
    counts = obj.aisle_counts(st)
    cur = best = obj.total(st)
    best_state = list(st)
    n, accepted, rejected_hard = obj.n, 0, 0
    t0 = time.perf_counter()
    cooling = (t_end / t_start) ** (1 / max(1, iterations - 1))
    T = t_start
    start_total = cur
    for _ in range(iterations):
        i, j = rng.sample(range(n), 2)
        if not obj.swap_ok(st, i, j, counts):
            rejected_hard += 1
            T *= cooling
            continue
        dJ, _, _ = obj.swap_delta(st, i, j)
        if dJ <= 0 or rng.random() < math.exp(-dJ / T):
            obj.apply_swap(st, counts, i, j)
            cur += dJ
            accepted += 1
            if cur < best - 1e-12:
                best, best_state = cur, list(st)
        T *= cooling
    final = obj.layout_from_state(best_state)
    bs = best_state
    e, c = obj.excess(bs)
    return final, {
        "iterations": iterations, "accepted_moves": accepted, "rejected_hard_constraint": rejected_hard,
        "initial_objective": round(start_total, 4), "final_objective": round(obj.total(bs), 4),
        "final_wwd": round(obj.wwd(bs), 4), "final_pair_violations": c, "final_total_excess": e,
        "seconds": round(time.perf_counter() - t0, 2),
    }
