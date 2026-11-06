import random, unittest
from tests.common import fixtures
from src.optimization import Objective, build_demand_layout, simulated_annealing
from src.search_algorithms import greedy_best_first, bounded_ucs, astar_variant, MAX_DEPTH
from src.validation import validate_layout, hard_basic_ok


def setup():
    f = fixtures(); obj = Objective(f["products"], f["slots"], f["pairs"])
    return f, obj, build_demand_layout(f["products"], f["slots"], "demand")


class TestObjective(unittest.TestCase):
    def test_incremental_delta_equals_full_recompute(self):
        f, obj, nn = setup(); st = obj.state_from_layout(nn); rg = random.Random(3)
        for _ in range(500):
            i, j = rg.sample(range(obj.n), 2)
            dJ = obj.swap_delta(st, i, j)[0]
            s2 = list(st); s2[i], s2[j] = s2[j], s2[i]
            self.assertAlmostEqual(obj.total(s2) - obj.total(st), dJ, places=9)


class TestSearch(unittest.TestCase):
    def test_each_algorithm_keeps_hard_rules_and_never_worsens(self):
        f, obj, nn = setup()
        for fn in (greedy_best_first, bounded_ucs, astar_variant):
            lay, info = fn(obj, nn, max_expansions=15)
            rep = validate_layout(f["products"], lay, f["slots"], f["pairs"])
            self.assertTrue(hard_basic_ok(rep), fn.__name__)
            self.assertLessEqual(info["final_objective"], info["initial_objective"] + 1e-9)
            self.assertLessEqual(info["swaps"], MAX_DEPTH)
            self.assertLessEqual(info["expanded_nodes"], 15)
            self.assertGreaterEqual(info["generated_nodes"], info["expanded_nodes"] if info["swaps"] else 0)

    def test_every_swap_in_path_is_legal(self):
        f, obj, nn = setup()
        for fn in (greedy_best_first, bounded_ucs, astar_variant):
            lay, info = fn(obj, nn, max_expansions=15)
            st = obj.state_from_layout(nn); counts = obj.aisle_counts(st); conflicts0 = obj.aisle_conflicts(st)
            for a, b in info["swap_list"]:
                i, j = obj.idx[a], obj.idx[b]
                self.assertTrue(obj.swap_ok(st, i, j, counts))
                obj.apply_swap(st, counts, i, j)
                self.assertLessEqual(obj.aisle_conflicts(st), conflicts0)
            self.assertEqual(obj.layout_from_state(st), lay)

    def test_target_flag_honest(self):
        f, obj, nn = setup()
        lay, info = bounded_ucs(obj, nn, max_expansions=3)
        self.assertEqual(info["target_reached"], info["final_objective"] <= info["target_objective"] + 1e-9)

    def test_simulated_annealing_hard_rules_and_improvement(self):
        f, obj, nn = setup()
        lay, info = simulated_annealing(nn, obj, iterations=5000, seed=1)
        self.assertTrue(hard_basic_ok(validate_layout(f["products"], lay, f["slots"], f["pairs"])))
        self.assertLess(info["final_objective"], info["initial_objective"])
        self.assertLessEqual(obj.aisle_conflicts(obj.state_from_layout(lay)), obj.aisle_conflicts(obj.state_from_layout(nn)))


if __name__ == "__main__":
    unittest.main()
