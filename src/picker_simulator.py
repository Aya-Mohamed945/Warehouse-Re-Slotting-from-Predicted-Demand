"""Picker-distance simulator on REAL held-out invoices.

Route model (identical for every layout): the picker starts at the Depot, repeatedly walks
(Manhattan distance) to the NEAREST not-yet-visited product location of the invoice, and
finally returns to the Depot. Ties are broken deterministically (distance, row, col, product id).
This is a nearest-neighbour heuristic, NOT an optimal travelling-salesperson route.
One visit per distinct product per invoice (test_orders.csv has no quantities)."""
from .warehouse import DEPOT


def build_invoices(orders_df, product_ids=None):
    """-> dict invoice -> sorted list of distinct product ids (optionally only known products)."""
    g = {}
    for inv, code in zip(orders_df["Invoice"], orders_df["StockCode"]):
        g.setdefault(inv, set()).add(code)
    keep = set(product_ids) if product_ids is not None else None
    return {inv: sorted(c for c in codes if keep is None or c in keep) for inv, codes in g.items()}


def route_distance(points):
    """points: list of (row, col, pid). Returns total NN-route length from/to the Depot."""
    cur, rem, total = DEPOT, list(points), 0
    while rem:
        best = min(rem, key=lambda p: (abs(cur[0] - p[0]) + abs(cur[1] - p[1]), p[0], p[1], p[2]))
        total += abs(cur[0] - best[0]) + abs(cur[1] - best[1])
        cur = (best[0], best[1])
        rem.remove(best)
    return total + abs(cur[0] - DEPOT[0]) + abs(cur[1] - DEPOT[1])


def evaluate_layout(layout, slots, invoices):
    """layout: pid -> slot id; invoices: dict inv -> [pid]. Returns metric dict."""
    pos = {s.slot_id: (s.row, s.col) for s in slots}
    where = {pid: pos[sid] for pid, sid in layout.items()}
    total = n_inv = lines_matched = lines_total = 0
    for inv, pids in invoices.items():
        pts = [(where[p][0], where[p][1], p) for p in pids if p in where]
        lines_total += len(pids)
        lines_matched += len(pts)
        if not pts:
            continue
        total += route_distance(pts)
        n_inv += 1
    return {
        "invoices_evaluated": n_inv,
        "product_line_coverage_pct": round(100 * lines_matched / lines_total, 2) if lines_total else 0.0,
        "total_picker_distance": total,
        "avg_distance_per_invoice": round(total / n_inv, 3) if n_inv else 0.0,
    }


def split_invoices(invoice_ids, dev_n=1000, seed=2026):
    """Reproduces the original development/holdout split: shuffle (seed 2026) the invoice ids in
    file order, first `dev_n` = development, the rest = reserved holdout."""
    import random
    ids = list(invoice_ids)
    random.Random(seed).shuffle(ids)
    return set(ids[:dev_n]), set(ids[dev_n:])
