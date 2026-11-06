"""Shared, pre-indexed CSP model used by BT, BT+FC and BT+FC+AC-3.

Variables : products (in the given order, normally highest predicted demand first)
Domains   : slots, stored as Python-int BIT MASKS. Bit i = i-th slot in Depot-distance order,
            so the lowest set bit is always the slot closest to the Depot (value ordering).
Constraints (all HARD):
  unary   : capacity, heavy -> low shelf             (static domain filter)
  alldiff : one product per slot
  binary  : co-purchase  manhattan(slot_a, slot_b) <= max_distance      (per listed pair)
  binary  : incompatible categories not in the same aisle               (all such product pairs)
"""
import time
from .constraints import categories_incompatible, build_pair_index, static_slot_ok
from .warehouse import manhattan, DEPOT

SOLVED, NO_SOLUTION = "SOLVED", "NO SOLUTION"
NODE_LIMIT, TIME_LIMIT = "NODE LIMIT REACHED", "TIME LIMIT REACHED"
INFEASIBLE_CERT = "INFEASIBLE BY CERTIFICATE"


def bits(mask):
    """Iterate set bits low -> high."""
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


def popcount(x):
    return x.bit_count()


class CSPModel:
    def __init__(self, products, slots, pair_constraints, enforce_category=True):
        self.products = list(products)
        self.n = len(self.products)
        self.slots_sorted = sorted(slots, key=lambda s: (manhattan(s.pos, DEPOT), s.row, s.col))
        self.m = len(self.slots_sorted)
        self.slot_id = [s.slot_id for s in self.slots_sorted]
        self.aisle = [s.aisle for s in self.slots_sorted]
        self.aisles = sorted(set(self.aisle))
        self.aisle_mask = {k: sum(1 << i for i in range(self.m) if self.aisle[i] == k)
                           for k in self.aisles}
        self.full = (1 << self.m) - 1
        self.pair_constraints = [(str(a), str(b), d) for a, b, d, *_ in pair_constraints]
        self.idx = {str(p["id"]): i for i, p in enumerate(self.products)}
        # distance balls: ball[d][i] = mask of slots within Manhattan distance d of slot i
        limits = sorted({d for _, _, d in self.pair_constraints})
        pos = [s.pos for s in self.slots_sorted]
        self.ball = {d: [sum(1 << j for j in range(self.m) if manhattan(pos[i], pos[j]) <= d)
                         for i in range(self.m)] for d in limits}
        # static (unary) domains
        self.static_dom = []
        for p in self.products:
            mask = 0
            for i, s in enumerate(self.slots_sorted):
                if static_slot_ok(p, s):
                    mask |= 1 << i
            self.static_dom.append(mask)
        # pair neighbours (only pairs whose both ends are variables)
        self.pair_nbrs = [dict() for _ in range(self.n)]
        for a, b, d in self.pair_constraints:
            if a in self.idx and b in self.idx:
                i, j = self.idx[a], self.idx[b]
                self.pair_nbrs[i][j] = d
                self.pair_nbrs[j][i] = d
        self.n_pairs_used = sum(len(x) for x in self.pair_nbrs) // 2
        # category-conflict neighbours
        self.enforce_category = enforce_category
        self.cat_nbrs = [[] for _ in range(self.n)]
        for i in range(self.n):
            for j in range(i + 1, self.n):
                if enforce_category and categories_incompatible(self.products[i]["category"], self.products[j]["category"]):
                    self.cat_nbrs[i].append(j)
                    self.cat_nbrs[j].append(i)
        self.degree = [len(self.pair_nbrs[i]) + len(self.cat_nbrs[i]) for i in range(self.n)]
        self.pair_index = build_pair_index(self.pair_constraints)

    # ---- helpers -------------------------------------------------------------------------
    def to_layout(self, assign):
        return {str(self.products[i]["id"]): self.slot_id[s] for i, s in enumerate(assign)}


class Stats:
    def __init__(self, max_nodes, max_seconds):
        self.max_nodes, self.max_seconds = max_nodes, max_seconds
        self.start = time.perf_counter()
        self.nodes = self.backtracks = self.checks = self.reductions = 0
        self.ac3_revisions = self.ac3_checks = self.ac3_domain_changes = 0
        self.limit = None

    def elapsed(self):
        return time.perf_counter() - self.start

    def hit_limit(self):
        if self.nodes >= self.max_nodes:
            self.limit = NODE_LIMIT
        elif self.elapsed() >= self.max_seconds:
            self.limit = TIME_LIMIT
        return self.limit is not None

    def result(self, model, assign, solved):
        status = SOLVED if solved else (self.limit or NO_SOLUTION)
        return {
            "status": status,
            "layout": model.to_layout(assign) if solved else None,
            "nodes": self.nodes, "backtracks": self.backtracks,
            "constraint_checks": self.checks + self.ac3_checks,
            "domain_reductions": self.reductions,
            "ac3_revisions": self.ac3_revisions, "ac3_domain_changes": self.ac3_domain_changes,
            "seconds": round(self.elapsed(), 4),
        }
