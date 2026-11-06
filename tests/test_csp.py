import tempfile, unittest
from tests.common import fixtures
from src.csp_model import CSPModel, bits
from src.csp_backtracking import solve_bt
from src.csp_forward_checking import solve_fc
from src.csp_ac3 import solve_fc_ac3, build_arcs, ac3_propagate
from src.csp_model import Stats
from src.validation import validate_layout
from src.experiments import run_csp_case


def subset(n, k):
    f = fixtures(); sub = f["products"][:n]; ids = {p["id"] for p in sub}
    return sub, [x for x in f["pairs"] if x[0] in ids and x[1] in ids][:k]


class TestCSP(unittest.TestCase):
    def test_all_algorithms_solve_easy_instance(self):
        sub, pairs = subset(10, 0)
        model = CSPModel(sub, fixtures()["slots"], pairs)
        for fn in (solve_bt, solve_fc, solve_fc_ac3):
            r = fn(model, max_seconds=10)
            self.assertEqual(r["status"], "SOLVED", fn.__name__)
            self.assertTrue(validate_layout(sub, r["layout"], fixtures()["slots"], pairs)["valid"])

    def test_smoke_30_products(self):
        sub, pairs = subset(30, 10)
        model = CSPModel(sub, fixtures()["slots"], pairs)
        for fn in (solve_fc, solve_fc_ac3):
            r = fn(model, max_seconds=10)
            self.assertEqual(r["status"], "SOLVED")
            self.assertTrue(validate_layout(sub, r["layout"], fixtures()["slots"], pairs)["valid"])
            self.assertGreater(r["constraint_checks"], 0)

    def test_60_products_strict(self):
        sub, pairs = subset(60, 20)
        model = CSPModel(sub, fixtures()["slots"], pairs)
        r = solve_fc(model, max_seconds=10)
        self.assertEqual(r["status"], "SOLVED")
        self.assertTrue(validate_layout(sub, r["layout"], fixtures()["slots"], pairs)["valid"])

    def test_limit_is_never_no_solution(self):
        sub, pairs = subset(120, 40)
        model = CSPModel(sub, fixtures()["slots"], pairs)
        self.assertEqual(solve_fc(model, max_nodes=30)["status"], "NODE LIMIT REACHED")
        self.assertEqual(solve_bt(model, max_seconds=0.05)["status"], "TIME LIMIT REACHED")

    def test_exhausted_search_reports_no_solution(self):
        # two products must be within distance 1 but sit in incompatible categories sharing only one aisle-free option
        from tests.common import prod
        from src.warehouse import Slot
        slots = [Slot(0, 0, 0, "low", 100), Slot(1, 0, 5, "low", 100)]          # two slots 5 apart
        ps = [prod("a"), prod("b")]
        model = CSPModel(ps, slots, [("a", "b", 1, 1.0)])
        for fn in (solve_bt, solve_fc, solve_fc_ac3):
            self.assertEqual(fn(model)["status"], "NO SOLUTION", fn.__name__)

    def test_ac3_prunes_and_detects_wipeout(self):
        from tests.common import prod
        from src.warehouse import Slot
        slots = [Slot(0, 0, 0, "low", 100), Slot(1, 0, 1, "low", 100), Slot(2, 0, 9, "low", 100)]
        ps = [prod("a"), prod("b")]
        model = CSPModel(ps, slots, [("a", "b", 1, 1.0)])
        dom = [0b111, 0b011]; st = Stats(10**6, 10)      # b restricted to the two near slots
        ok = ac3_propagate(model, dom, build_arcs(model), None, [], st, [-1, -1])
        self.assertTrue(ok)
        self.assertEqual(bin(dom[0]).count("1"), 2)          # far slot (col 9) has no support and is removed
        self.assertGreater(st.ac3_revisions, 0); self.assertGreater(st.ac3_domain_changes, 0)
        dom2 = [1 << 2, 1 << 0]                               # a only far slot, b only near: wipe-out
        self.assertFalse(ac3_propagate(model, dom2, build_arcs(model), None, [], Stats(10**6, 10), [-1, -1]))

    def test_domain_restoration(self):
        sub, pairs = subset(30, 10)
        model = CSPModel(sub, fixtures()["slots"], pairs)
        r1 = solve_fc(model, max_seconds=10); r2 = solve_fc(model, max_seconds=10)
        self.assertEqual(r1["layout"], r2["layout"])          # deterministic and model not corrupted between runs

    def test_certificate_short_circuit(self):
        with tempfile.TemporaryDirectory() as d:
            f = fixtures()
            r = run_csp_case(f["products"], f["slots"], f["pairs"], 120, 40, "BT+FC", "test", d)
            self.assertEqual(r["Status"], "INFEASIBLE BY CERTIFICATE"); self.assertEqual(r["Nodes"], 0)


if __name__ == "__main__":
    unittest.main()
