"""Final automated QA suite. A test is PASS only if it ran and passed; FAIL results are reported as
such (several FAILs are EXPECTED consequences of the documented infeasibility - see Details)."""
import inspect
import os
import pandas as pd
from .constraints import categories_incompatible, aisle_capacity_certificate
from .validation import validate_layout, hard_basic_ok
from .picker_simulator import evaluate_layout
from .optimization import Objective

EXPECTED_COLUMNS = {
    "results/layouts/random_layout.csv": {"product_id", "slot_id", "row", "col", "aisle", "level", "category", "heavy", "predicted_demand", "last_week_demand"},
    "results/layouts/last_week_layout.csv": {"product_id", "slot_id"},
    "results/layouts/nn_layout.csv": {"product_id", "slot_id"},
    "results/layouts/nn_swaps_layout.csv": {"product_id", "slot_id"},
    "results/experiments/csp_comparison.csv": {"Products", "Algorithm", "Pair constraints", "Status", "Nodes", "Backtracks", "Constraint checks", "Time (s)", "Valid layout"},
    "results/experiments/search_comparison.csv": {"Algorithm", "initial_objective", "final_objective", "swaps", "expanded_nodes", "generated_nodes", "seconds", "target_reached", "final_hard_rules_ok"},
    "results/experiments/four_layout_comparison.csv": {"Layout", "Invoices evaluated", "Average distance per invoice", "Total picker distance", "Pair violations", "Total excess distance"},
    "results/validation/remaining_pair_violations.csv": {"layout", "product_a", "product_b", "distance", "max_distance", "excess"},
    "results/validation/layout_validation_summary.csv": {"layout", "total_products", "valid"},
}


BASIC_TESTS = ("Product assignment", "Unique slots", "Capacity", "Heavy products")


def _row(rows, test, ok, details, status=None, scope=None):
    scope = scope or ("basic" if test.startswith(BASIC_TESTS) else "strict" if ("aisle rule" in test or "co-purchase" in test) else "integration")
    rows.append({"Test": test, "Scope": scope, "Result": status or ("PASS" if ok else "FAIL"), "Details": details})


def run_qa(ctx, root):
    P, S, pairs, layouts = ctx["products"], ctx["slots"], ctx["pairs"], ctx["layouts"]
    rows = []
    reps = {n: validate_layout(P, l, S, pairs) for n, l in layouts.items()}

    ok = all(r["assigned_products"] == 120 and not r["missing_products"] and not r["unknown_products"] for r in reps.values())
    _row(rows, "Product assignment (all 120 assigned, none missing) - 4 layouts", ok, {n: r["assigned_products"] for n, r in reps.items()})
    ok = all(not r["duplicate_slots"] and not r["invalid_slot_ids"] and len(set(l.values())) == 120 for (n, l), r in zip(layouts.items(), reps.values()))
    _row(rows, "Unique slots (120 distinct valid slots) - 4 layouts", ok, "no duplicate or unknown slot ids")
    _row(rows, "Capacity", all(not r["capacity_violations"] for r in reps.values()),
         "0 violations in all four layouts (NB: every slot has capacity 100 and needs are 1-80, so the rule never binds)")
    _row(rows, "Heavy products on low shelves", all(not r["heavy_shelf_violations"] for r in reps.values()), "0 violations in all four layouts")
    unit = all(categories_incompatible(a, b) == categories_incompatible(b, a) for a in ["food", "cleaning", "stationery", "fragile"] for b in ["food", "cleaning", "stationery", "fragile"]) \
        and categories_incompatible("cleaning", "food") and categories_incompatible("cleaning", "fragile") \
        and not any(categories_incompatible(a, b) for a, b in [("cleaning", "stationery"), ("food", "fragile"), ("food", "stationery"), ("fragile", "stationery"), ("food", "food"), ("cleaning", "cleaning")])
    _row(rows, "Category compatibility function (symmetric, matches specified table)", unit, "10 unordered pairs + 4 same-category cases checked")
    cert = ctx["cert"]
    counts = {n: len(r["incompatible_aisle_violations"]) for n, r in reps.items()}
    _row(rows, "Category-aisle rule on the 4 full 120-product layouts", all(v == 0 for v in counts.values()),
         f"incompatible same-aisle product pairs: {counts}. Counting certificate says a violation-free 120-layout is "
         f"{'possible' if cert['feasible'] else 'IMPOSSIBLE'}: {cert['detail']}")
    csp = ctx["csp_df"]
    solved = csp[csp.Status == "SOLVED"]
    _row(rows, "CSP-solved layouts (strict rules, 60/90 products) satisfy ALL hard constraints", bool((solved["Valid layout"] == "yes").all()) and len(solved) > 0,
         f"{len(solved)} solved runs, all validated with validate_layout (incl. hard pair distances and aisle rule)")
    cert_by_n = {n: aisle_capacity_certificate(P[:n], S)["feasible"] for n in (60, 90, 120)}
    infeasible_rows = set(csp[csp.Status == "INFEASIBLE BY CERTIFICATE"]["Products"])
    _row(rows, "INFEASIBLE BY CERTIFICATE status appears exactly where the exact certificate fails", infeasible_rows == {n for n, ok in cert_by_n.items() if not ok},
         f"certificate feasible? {cert_by_n}; rows marked infeasible: {sorted(infeasible_rows)}", scope="strict")
    nn_csv = pd.read_csv(os.path.join(root, "results", "layouts", "nn_layout.csv"))      # independent re-read of exported data
    cl = int((nn_csv["category"] == "cleaning").sum()); fb = int(nn_csv["category"].isin(["food", "fragile"]).sum())
    _row(rows, "Certificate inputs recomputed from the real data", cl == ctx["cert_counts"][0] and fb == ctx["cert_counts"][1],
         f"cleaning={cl}, food+fragile={fb}, aisles={sorted({s.aisle for s in S})} x {len(S)//4} slots; strict 120-product layout feasible = {cert['feasible']}")
    _row(rows, "Layouts reported 'valid' really are valid", all(not r["valid"] or (not r["pair_violations"] and not r["incompatible_aisle_violations"]) for r in reps.values()),
         {n: r["valid"] for n, r in reps.items()})
    pv = {n: len(r["pair_violations"]) for n, r in reps.items()}
    _row(rows, "Hard co-purchase constraints satisfied on the 4 full layouts", all(v == 0 for v in pv.values()),
         f"pair violations remaining (soft objective, reported separately): {pv}")

    # search validity: replay swaps
    ok, detail = True, []
    obj = Objective(P, S, pairs)
    for name, res in ctx["search_results"].items():
        st = obj.state_from_layout(ctx["layouts"]["NN demand"])
        counts_ = obj.aisle_counts(st)
        for a, b in res["swap_list"]:
            i, j = obj.idx[a], obj.idx[b]
            good = obj.swap_ok(st, i, j, counts_)
            ok &= good
            obj.apply_swap(st, counts_, i, j)
        lay = obj.layout_from_state(st)
        rep = validate_layout(P, lay, S, pairs)
        ok &= hard_basic_ok(rep) and lay == ctx["search_layouts"][name]
        detail.append(f"{name}: {len(res['swap_list'])} swaps replayed")
    _row(rows, "Search validity (every swap keeps unique slot/capacity/heavy and does not add aisle conflicts)", ok, "; ".join(detail))

    # same products
    sets = {n: frozenset(l) for n, l in layouts.items()}
    _row(rows, "All four layouts use the same product set", len(set(sets.values())) == 1, f"{len(next(iter(sets.values())))} products")

    inv_hold, inv_dev = ctx["hold_inv"], ctx["dev_inv"]
    mets = {n: evaluate_layout(l, S, inv_hold) for n, l in layouts.items()}
    same = len({m["invoices_evaluated"] for m in mets.values()}) == 1
    _row(rows, "Test-order evaluation: same invoices, same simulator for all 4 layouts", same,
         f"{next(iter(mets.values()))['invoices_evaluated']} invoices each; coverage {sorted({m['product_line_coverage_pct'] for m in mets.values()})}%")
    cmp_df = ctx["four_df"]
    _row(rows, "Four-layout table reproduces from a fresh evaluation", all(
        abs(cmp_df.set_index("Layout").loc[n, "Average distance per invoice"] - mets[n]["avg_distance_per_invoice"]) < 1e-9 for n in layouts),
        "recomputed average distances equal the exported table")
    orders = ctx["data"]["orders"]
    _row(rows, "No duplicated (invoice, product) lines counted", not orders.duplicated(["Invoice", "StockCode"]).any(),
         f"{len(orders)} unique lines, {orders['Invoice'].nunique()} invoices")
    _row(rows, "Development / holdout invoices disjoint and exhaustive",
         set(inv_dev).isdisjoint(inv_hold) and len(inv_dev) + len(inv_hold) == orders["Invoice"].nunique(), f"{len(inv_dev)} dev + {len(inv_hold)} holdout")
    params = list(inspect.signature(Objective.__init__).parameters)
    free = not any("order" in p or "invoice" in p for p in params) and "invoice" not in inspect.getsource(Objective).lower()
    _row(rows, "No test-order information in the optimiser / search / CSP objective (final NN + Swaps)", free,
         "Objective, SA and Search use only predicted demand + training pair constraints. The LEGACY optimiser does tune on 1000 dev invoices (kept separately).")
    _row(rows, "Training/test leakage inside forecasts.csv & copurchase_pairs.csv", None,
         "Training window of these Person-1 files was not supplied, so this cannot be verified here.", status="NOT VERIFIABLE")

    # comparable CSP conditions
    g = csp.groupby(["Protocol", "Products"])["Pair constraints"].nunique()
    _row(rows, "CSP algorithms compared on identical problems", bool((g == 1).all()), "same pair-constraint set per (protocol, size) for BT / BT+FC / BT+FC+AC-3")

    # exports
    problems = []
    for rel, cols in EXPECTED_COLUMNS.items():
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            problems.append(f"missing {rel}")
            continue
        miss = cols - set(pd.read_csv(path).columns)
        if miss:
            problems.append(f"{rel} lacks {sorted(miss)}")
    _row(rows, "CSV exports exist with expected columns", not problems, problems or f"{len(EXPECTED_COLUMNS)} files checked")

    from .experiments import EXPECTED_FIGURES
    figs = EXPECTED_FIGURES
    bad = [f for f in figs if not (os.path.exists(os.path.join(root, "figures", f)) and os.path.getsize(os.path.join(root, "figures", f)) > 20000
           and os.path.exists(os.path.join(root, "figures", "data", f.replace(".png", "_data.csv"))))]
    _row(rows, "Figures exist (PNG) with their underlying data CSV", not bad, bad or f"{len(figs)} figures checked")
    fd = pd.read_csv(os.path.join(root, "figures", "data", "four_layout_distance_data.csv")).set_index("Layout")
    ok = all(abs(fd.loc[n, "Average distance per invoice"] - cmp_df.set_index("Layout").loc[n, "Average distance per invoice"]) < 1e-9 for n in layouts)
    sd = pd.read_csv(os.path.join(root, "figures", "data", "search_objective_data.csv")).set_index("Algorithm")
    sdf = ctx["search_df"].set_index("Algorithm")
    ok &= all(abs(sd.loc[a, "final_objective"] - sdf.loc[a, "final_objective"]) < 1e-9 for a in sdf.index)
    cd = pd.read_csv(os.path.join(root, "figures", "data", "csp_execution_time_data.csv"))
    plot_df = ctx["csp_plot_df"]
    ok &= len(cd) == len(plot_df) and abs(cd["Time (s)"].sum() - plot_df["Time (s)"].sum()) < 1e-6
    _row(rows, "Figure data equals the experiment result tables (no invented values)", ok, "four-layout, search and CSP figure data compared with exported results")
    import unittest
    loader = unittest.TestLoader()
    tdir = os.path.join(root, "tests")
    if os.path.isdir(tdir):
        import io
        suite = loader.discover(tdir, top_level_dir=root)
        res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        bad = [str(t[0]) for t in res.failures + res.errors]
        _row(rows, f"Automated unit tests (tests/ folder, {res.testsRun} tests)", not bad and res.testsRun > 0,
             f"{res.testsRun - len(bad)} passed, {len(bad)} failed {bad}", scope="unit")
    else:
        _row(rows, "Automated unit tests", None, "tests/ folder missing", status="NOT RUN", scope="unit")
    return pd.DataFrame(rows)
