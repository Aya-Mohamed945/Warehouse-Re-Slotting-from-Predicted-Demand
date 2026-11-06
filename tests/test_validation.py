import os, tempfile, unittest
import pandas as pd
from tests.common import fixtures, prod
from src.warehouse import create_warehouse, load_data, normalize_id
from src.validation import validate_layout, hard_basic_ok
from src.optimization import build_demand_layout, build_random_layout
from src.picker_simulator import route_distance, evaluate_layout, build_invoices, split_invoices


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.slots = create_warehouse()
        self.P = [prod("a", "cleaning"), prod("b", "food"), prod("c", "stationery", heavy=True)]

    def rep(self, layout, pairs=()):
        return validate_layout(self.P, layout, self.slots, list(pairs))

    def test_valid_layout(self):
        r = self.rep({"a": 0, "b": 3, "c": 24})            # c heavy on a low row (row 2)
        self.assertTrue(r["valid"], r)

    def test_missing_product(self):
        r = self.rep({"a": 0, "b": 3})
        self.assertEqual(r["missing_products"], ["c"]); self.assertFalse(r["valid"])

    def test_unknown_product_and_invalid_slot(self):
        r = self.rep({"a": 0, "b": 3, "c": 24, "zzz": 5})
        self.assertEqual(r["unknown_products"], ["zzz"])
        r = self.rep({"a": 0, "b": 3, "c": 999})
        self.assertEqual(r["invalid_slot_ids"], ["c"])

    def test_duplicate_slot(self):
        r = self.rep({"a": 0, "b": 0, "c": 24})
        self.assertIn(0, r["duplicate_slots"])

    def test_heavy_shelf(self):
        r = self.rep({"a": 0, "b": 3, "c": 119})            # heavy product on high shelf
        self.assertEqual(r["heavy_shelf_violations"], ["c"])

    def test_capacity(self):
        self.P[0]["required_capacity"] = 101
        r = self.rep({"a": 0, "b": 3, "c": 24})
        self.assertEqual(r["capacity_violations"], ["a"])

    def test_incompatible_aisle(self):
        r = self.rep({"a": 0, "b": 1, "c": 24})            # cleaning + food in aisle 0
        self.assertEqual(len(r["incompatible_aisle_violations"]), 1); self.assertFalse(r["valid"])

    def test_pair_distance_and_excess(self):
        r = self.rep({"a": 0, "b": 3, "c": 24}, [("a", "b", 2, 5.0)])      # distance 3 > 2
        self.assertEqual(r["pair_violations"], [("a", "b", 3, 2)]); self.assertEqual(r["total_excess_distance"], 1)
        r = self.rep({"a": 0, "b": 3, "c": 24}, [("a", "b", 3, 5.0)])
        self.assertTrue(r["valid"])

    def test_generated_layouts_pass_basic_rules(self):
        f = fixtures()
        for lay in (build_demand_layout(f["products"], f["slots"], "demand"), build_demand_layout(f["products"], f["slots"], "last_week_demand"),
                    build_random_layout(f["products"], f["slots"], 42)):
            r = validate_layout(f["products"], lay, f["slots"], f["pairs"])
            self.assertTrue(hard_basic_ok(r)); self.assertEqual(r["assigned_products"], 120)


class TestPicker(unittest.TestCase):
    def test_routes(self):
        self.assertEqual(route_distance([(2, 3, "x")]), 10)
        self.assertEqual(route_distance([(0, 1, "a"), (0, 3, "b")]), 6)

    def test_evaluate_and_split(self):
        slots = create_warehouse()
        m = evaluate_layout({"a": 1, "b": 3}, slots, {"i1": ["a", "b"], "i2": ["zzz"]})
        self.assertEqual(m["invoices_evaluated"], 1); self.assertEqual(m["total_picker_distance"], 6)
        d1, h1 = split_invoices([str(i) for i in range(50)], 10, 1); d2, h2 = split_invoices([str(i) for i in range(50)], 10, 1)
        self.assertEqual((d1, h1), (d2, h2)); self.assertFalse(d1 & h1)


class TestInputs(unittest.TestCase):
    def _write(self, d, inv_col="InvoiceNo", strength="12.5"):
        pd.DataFrame({"product_id": ["100.0", "200", "300"], "predicted_demand": ["5", "x", "7"], "last_week_demand": [1, 2, None]}).to_csv(f"{d}/forecasts.csv", index=False)
        pd.DataFrame({"product_a": ["100", "100", "300"], "product_b": ["300", "300", "100"], "strength": [strength, "20.25", "9"], "max_distance": [2, 2, 0]}).to_csv(f"{d}/copurchase_pairs.csv", index=False)
        pd.DataFrame({inv_col: ["A1", "A1", "A1", None], "StockCode": ["100.0", "300", "300", "100"]}).to_csv(f"{d}/test_orders.csv", index=False)

    def test_invoice_noinvoice_variants_and_cleaning(self):
        for col in ("InvoiceNo", "Invoice", "invoice_no"):
            with tempfile.TemporaryDirectory() as d:
                self._write(d, col)
                data, rep = load_data(d)
                self.assertEqual(rep["order_invoice_column_detected"], col)
                self.assertIn("Invoice", data["orders"].columns)
                self.assertEqual(list(data["forecasts"].product_id), ["100", "300"])         # '100.0' -> '100'; non-numeric demand row dropped
                self.assertEqual(rep["forecast_last_week_missing_filled_with_0"], 1)
                self.assertEqual(len(data["pairs"]), 1)                                      # duplicate kept strongest, invalid distance dropped
                self.assertEqual(float(data["pairs"].strength.iloc[0]), 20.25)               # decimal precision kept
                self.assertEqual(len(data["orders"]), 2)                                     # missing invoice + duplicate dropped

    def test_normalize_id(self):
        self.assertEqual(normalize_id("85123.0"), "85123"); self.assertEqual(normalize_id(" 85123A "), "85123A"); self.assertIsNone(normalize_id(float("nan")))


if __name__ == "__main__":
    unittest.main()
