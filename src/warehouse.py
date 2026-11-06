"""Warehouse geometry, data loading and (simulated) product attributes.

Everything here that is NOT in the UCI/forecast files (shelf levels, aisles,
slot capacity, product category / heavy flag / required capacity) is a
SIMULATED assumption and is documented in reports/assumptions_and_limitations.md.
"""
from dataclasses import dataclass
import os
import random
import pandas as pd

ROWS, COLS, DEPOT = 10, 12, (0, 0)
AISLE_WIDTH = 3            # aisle = col // 3  -> 4 aisles x 30 slots
SLOT_CAPACITY = 100
CATEGORIES = ["food", "cleaning", "stationery", "fragile"]
ATTRIBUTE_SEED = 42        # same seed/draw order as the original notebook


@dataclass(frozen=True)
class Slot:
    slot_id: int
    row: int
    col: int
    level: str
    capacity: int

    @property
    def aisle(self):
        return self.col // AISLE_WIDTH

    @property
    def pos(self):
        return (self.row, self.col)


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def create_warehouse():
    """10x12 grid; rows 0-3 low, 4-6 middle, 7-9 high (unchanged from original)."""
    slots = []
    for r in range(ROWS):
        level = "low" if r < 4 else ("middle" if r < 7 else "high")
        for c in range(COLS):
            slots.append(Slot(r * COLS + c, r, c, level, SLOT_CAPACITY))
    return slots


def normalize_id(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _find_col(df, candidates, label):
    """Case/underscore-insensitive column detection; raises a clear error if absent."""
    norm = {"".join(ch for ch in str(c).lower() if ch.isalnum()): c for c in df.columns}
    for cand in candidates:
        key = "".join(ch for ch in cand.lower() if ch.isalnum())
        if key in norm:
            return norm[key]
    raise ValueError(f"No {label} column found; tried {candidates}; columns are {list(df.columns)}")


def load_data(data_dir):
    """Load, normalise and validate the three inputs.

    Schema detection: invoice column may be Invoice / InvoiceNo / invoice_no ...; the product column
    of the orders may be StockCode / product_id. Everything is renamed to the canonical names used
    by the project (Invoice, StockCode); the CSV files on disk are never modified.
    Cleaning (all counted in the returned report): product ids normalised ('123.0' -> '123'),
    forecast rows with non-numeric predicted demand dropped, duplicate forecast ids keep the first,
    missing last_week_demand -> 0 (documented fallback), pairs with unknown products / non-positive
    or missing max_distance / non-numeric strength dropped, duplicate pairs keep the strongest,
    order lines without invoice or product dropped, duplicate (invoice, product) lines dropped.
    Strength keeps full float precision."""
    f = pd.read_csv(os.path.join(data_dir, "forecasts.csv"))
    c = pd.read_csv(os.path.join(data_dir, "copurchase_pairs.csv"))
    t = pd.read_csv(os.path.join(data_dir, "test_orders.csv"))
    f = f.rename(columns={_find_col(f, ["product_id", "StockCode", "product"], "forecast product id"): "product_id",
                          _find_col(f, ["predicted_demand", "forecast", "predicted"], "predicted demand"): "predicted_demand"})
    try:
        f = f.rename(columns={_find_col(f, ["last_week_demand", "last_week", "lastweekdemand"], "last-week demand"): "last_week_demand"})
    except ValueError:
        f["last_week_demand"] = float("nan")
    c = c.rename(columns={_find_col(c, ["product_a", "producta", "item_a"], "pair product A"): "product_a",
                          _find_col(c, ["product_b", "productb", "item_b"], "pair product B"): "product_b",
                          _find_col(c, ["strength", "weight", "count"], "pair strength"): "strength",
                          _find_col(c, ["max_distance", "maxdistance", "max_dist"], "pair max distance"): "max_distance"})
    inv = _find_col(t, ["Invoice", "InvoiceNo", "invoice_no", "invoice_id", "order_id"], "invoice")
    prod = _find_col(t, ["StockCode", "product_id", "stock_code", "product"], "order product")
    t = t.rename(columns={inv: "Invoice", prod: "StockCode"})

    report = {"forecast_rows_raw": len(f), "pair_rows_raw": len(c), "order_rows_raw": len(t),
              "order_invoice_column_detected": inv, "order_product_column_detected": prod}
    f["product_id"] = f["product_id"].map(normalize_id)
    for col in ("predicted_demand", "last_week_demand"):
        f[col] = pd.to_numeric(f[col], errors="coerce")
    bad = f["product_id"].isna() | f["predicted_demand"].isna()
    report["forecast_rows_dropped_invalid"] = int(bad.sum())
    f = f[~bad]
    report["forecast_duplicate_ids_dropped"] = int(f["product_id"].duplicated().sum())
    f = f.drop_duplicates("product_id", keep="first")
    report["forecast_last_week_missing_filled_with_0"] = int(f["last_week_demand"].isna().sum())
    f["last_week_demand"] = f["last_week_demand"].fillna(0.0)
    f = f.reset_index(drop=True)
    ids = set(f["product_id"])

    c["product_a"], c["product_b"] = c["product_a"].map(normalize_id), c["product_b"].map(normalize_id)
    c["strength"] = pd.to_numeric(c["strength"], errors="coerce").astype(float)       # never truncated
    c["max_distance"] = pd.to_numeric(c["max_distance"], errors="coerce")
    bad = (c["product_a"].isna() | c["product_b"].isna() | c["strength"].isna() | c["max_distance"].isna()
           | (c["max_distance"] <= 0) | (c["product_a"] == c["product_b"]))
    report["pair_rows_dropped_invalid"] = int(bad.sum())
    c = c[~bad]
    unknown = ~(c["product_a"].isin(ids) & c["product_b"].isin(ids))
    report["pair_rows_dropped_unknown_product"] = int(unknown.sum())
    c = c[~unknown]
    c["max_distance"] = c["max_distance"].astype(int)
    c["_k"] = c.apply(lambda r: frozenset((r.product_a, r.product_b)), axis=1)
    c = c.sort_values("strength", ascending=False, kind="stable")
    report["pair_duplicates_dropped"] = int(c["_k"].duplicated().sum())
    c = c.drop_duplicates("_k").drop(columns="_k").reset_index(drop=True)

    t["Invoice"] = t["Invoice"].map(lambda v: None if pd.isna(v) else str(v).strip())
    t["StockCode"] = t["StockCode"].map(normalize_id)
    bad = t["Invoice"].isna() | t["StockCode"].isna() | (t["Invoice"] == "")
    report["order_lines_dropped_missing_id"] = int(bad.sum())
    t = t[~bad]
    report["order_duplicate_lines_dropped"] = int(t.duplicated(["Invoice", "StockCode"]).sum())
    t = t.drop_duplicates(["Invoice", "StockCode"]).reset_index(drop=True)
    report["order_products_not_in_forecasts"] = len(set(t.StockCode) - ids)
    report.update({"forecast_rows": len(f), "pair_rows": len(c), "pair_unique_products": len(set(c.product_a) | set(c.product_b)),
                   "order_lines": len(t), "order_invoices": int(t["Invoice"].nunique()),
                   "order_has_quantity_column": "Quantity" in t.columns})
    if len(f) == 0 or len(c) == 0 or len(t) == 0:
        raise ValueError(f"Empty input after validation: {report}")
    return {"forecasts": f, "pairs": c, "orders": t}, report


def build_products(forecasts):
    """Real demand + simulated category/heavy/capacity. Draw order identical to the
    original notebook (seed 42, forecast-file order) so attributes are preserved.
    Returned sorted by predicted demand, highest first."""
    rng = random.Random(ATTRIBUTE_SEED)
    products = []
    for _, r in forecasts.iterrows():
        products.append({
            "id": str(r["product_id"]),
            "demand": float(r["predicted_demand"]),
            "last_week_demand": float(r["last_week_demand"]),
            "heavy": rng.random() < 0.15,
            "category": rng.choice(CATEGORIES),
            "required_capacity": rng.randint(1, 80),
        })
    products.sort(key=lambda p: p["demand"], reverse=True)
    return products


def build_pair_constraints(pairs_df, product_ids):
    """List of (a, b, max_distance, strength), strongest first, restricted to known products."""
    ids = set(product_ids)
    d = pairs_df[pairs_df.product_a.isin(ids) & pairs_df.product_b.isin(ids)
                 & pairs_df.max_distance.notna()]
    d = d.sort_values(["strength", "product_a", "product_b"], ascending=[False, True, True])
    return [(r.product_a, r.product_b, int(r.max_distance), float(r.strength))
            for r in d.itertuples()]
