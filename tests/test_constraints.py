import unittest
from tests.common import fixtures, prod
from src.warehouse import manhattan, create_warehouse, Slot
from src.constraints import (categories_incompatible, build_pair_index, static_slot_ok, is_valid_slot,
                             aisle_capacity_certificate, incompatible_aisle_pairs)

CATS = ["cleaning", "food", "fragile", "stationery"]


class TestCategories(unittest.TestCase):
    def test_symmetry(self):
        for a in CATS:
            for b in CATS:
                self.assertEqual(categories_incompatible(a, b), categories_incompatible(b, a))

    def test_rule_table(self):
        self.assertTrue(categories_incompatible("cleaning", "food"))
        self.assertTrue(categories_incompatible("cleaning", "fragile"))
        for a, b in [("cleaning", "stationery"), ("food", "fragile"), ("food", "stationery"), ("fragile", "stationery")]:
            self.assertFalse(categories_incompatible(a, b), (a, b))

    def test_same_category_compatible(self):
        for c in CATS:
            self.assertFalse(categories_incompatible(c, c))


class TestGeometry(unittest.TestCase):
    def test_manhattan(self):
        self.assertEqual(manhattan((0, 0), (2, 3)), 5)
        self.assertEqual(manhattan((4, 7), (1, 9)), 5)
        self.assertEqual(manhattan((3, 3), (3, 3)), 0)

    def test_warehouse_shape(self):
        s = create_warehouse()
        self.assertEqual(len(s), 120)
        self.assertEqual(len({x.slot_id for x in s}), 120)
        self.assertEqual({x.aisle for x in s}, {0, 1, 2, 3})
        for a in range(4):
            self.assertEqual(sum(x.aisle == a for x in s), 30)
        self.assertEqual({x.level for x in s}, {"low", "middle", "high"})


class TestPairIndex(unittest.TestCase):
    def test_index_matches_bruteforce(self):
        pairs = fixtures()["pairs"]
        idx = build_pair_index(pairs)
        for pid, nbrs in idx.items():
            brute = sorted([(b if a == pid else a, d) for a, b, d, *_ in pairs if pid in (a, b)])
            self.assertEqual(sorted(nbrs), brute)
        self.assertEqual(sum(len(v) for v in idx.values()), 2 * len(pairs))

    def test_strength_precision_kept(self):
        idx_pairs = [("a", "b", 2, 12.75)]
        self.assertEqual(idx_pairs[0][3], 12.75)
        self.assertIsInstance(fixtures()["pairs"][0][3], float)


class TestSlotRules(unittest.TestCase):
    def test_capacity_and_heavy(self):
        slots = create_warehouse()
        low, high = slots[0], slots[-1]
        self.assertTrue(static_slot_ok(prod("p", heavy=True), low))
        self.assertFalse(static_slot_ok(prod("p", heavy=True), high))
        self.assertTrue(static_slot_ok(prod("p", heavy=False), high))
        self.assertFalse(static_slot_ok(prod("p", cap=101), low))

    def test_is_valid_slot_aisle_and_distance(self):
        slots = create_warehouse(); sby = {s.slot_id: s for s in slots}
        a, b = prod("a", "cleaning"), prod("b", "food")
        pby = {"a": a, "b": b}
        layout = {"a": 0}                                    # aisle 0
        self.assertFalse(is_valid_slot(b, sby[1], layout, sby, pby, {}))      # same aisle, incompatible
        self.assertTrue(is_valid_slot(b, sby[3], layout, sby, pby, {}))       # aisle 1
        self.assertFalse(is_valid_slot(b, sby[0], layout, sby, pby, {}))      # occupied
        idx = build_pair_index([("a", "b", 2, 1.0)])
        self.assertFalse(is_valid_slot(b, sby[11], layout, sby, pby, idx))    # too far (distance 11)


class TestCertificate(unittest.TestCase):
    def test_real_full_problem_infeasible(self):
        f = fixtures()
        cert = aisle_capacity_certificate(f["products"], f["slots"])
        n_c = sum(p["category"] == "cleaning" for p in f["products"])
        n_fb = sum(p["category"] in ("food", "fragile") for p in f["products"])
        self.assertEqual((n_c > 30 and n_fb > 60), not cert["feasible"])     # the 31 / 61 pigeonhole
        self.assertFalse(cert["feasible"])

    def test_feasible_small_case(self):
        f = fixtures()
        ps = [prod(f"c{i}", "cleaning") for i in range(20)] + [prod(f"f{i}", "food") for i in range(40)]
        self.assertTrue(aisle_capacity_certificate(ps, f["slots"])["feasible"])

    def test_certificate_agrees_with_bruteforce_tiny(self):
        # 2 aisles x 2 slots: 3 cleaning + 1 food cannot fit (cleaning needs both aisles)
        slots = [Slot(i, 0, i, "low", 100) for i in range(4)]
        import src.warehouse as W
        old = W.AISLE_WIDTH
        class S2(Slot):
            @property
            def aisle(self): return self.col // 2
        slots = [S2(i, 0, i, "low", 100) for i in range(4)]
        ps = [prod("c1", "cleaning"), prod("c2", "cleaning"), prod("c3", "cleaning"), prod("f", "food")]
        self.assertFalse(aisle_capacity_certificate(ps, slots)["feasible"])
        ps = [prod("c1", "cleaning"), prod("c2", "cleaning"), prod("f1", "food"), prod("f2", "food")]
        self.assertTrue(aisle_capacity_certificate(ps, slots)["feasible"])

    def test_incompatible_pairs_listing(self):
        slots = create_warehouse(); sby = {s.slot_id: s for s in slots}
        pby = {"a": prod("a", "cleaning"), "b": prod("b", "food"), "c": prod("c", "stationery")}
        self.assertEqual(len(incompatible_aisle_pairs({"a": 0, "b": 1, "c": 2}, pby, sby)), 1)
        self.assertEqual(len(incompatible_aisle_pairs({"a": 0, "b": 3, "c": 2}, pby, sby)), 0)


if __name__ == "__main__":
    unittest.main()
