"""Experiment runners, cached CSP benchmark, and the single entry point `run_complete_project`.

Each pipeline step is a small function that takes/returns the shared context dict `ctx`, so the
notebook can run (and display) the steps one by one while `run_complete_project` runs them all."""
import json
import os
import pandas as pd

from .warehouse import (load_data, create_warehouse, build_products, build_pair_constraints, DEPOT)
from .constraints import aisle_capacity_certificate
from .csp_model import CSPModel, INFEASIBLE_CERT
from .csp_backtracking import solve_bt
from .csp_forward_checking import solve_fc
from .csp_ac3 import solve_fc_ac3
from .validation import validate_layout, report_summary, hard_basic_ok
from .optimization import Objective, LAMBDA, build_demand_layout, build_random_layout, simulated_annealing
from .search_algorithms import greedy_best_first, bounded_ucs, astar_variant
from .picker_simulator import build_invoices, evaluate_layout, split_invoices

ALGORITHMS = {"BT": solve_bt, "BT+FC": solve_fc, "BT+FC+AC-3": solve_fc_ac3}
MAX_SECONDS, MAX_NODES = 20.0, 2_000_000
DIAG_SECONDS = 45.0       # the relaxed 120-product diagnostic is borderline at 20 s (machine dependent), so it gets a longer, documented limit
PROTOCOLS = {"A (20/30/40 strongest pairs)": {60: 20, 90: 30, 120: 40},
             "B (30 strongest pairs)": {60: 30, 90: 30, 120: 30}}
DIAG_LABEL = "Diagnostic: 120 products, aisle rule RELAXED"
SA_ITERATIONS, SEED, DEV_INVOICES, SPLIT_SEED = 100_000, 42, 1000, 2026
SEARCH_RUNS = {"Greedy Best-First": greedy_best_first, "Bounded UCS": bounded_ucs, "A* variant": astar_variant}
LAYOUT_FILES = {"Random": "random_layout", "Last-week demand": "last_week_layout", "NN demand": "nn_layout", "NN + Swaps": "nn_swaps_layout"}
EXPECTED_FIGURES = ["warehouse_layout.png", "copurchase_network.png", "demand_distribution.png", "csp_execution_time.png",
                    "csp_search_nodes.png", "csp_backtracks.png", "search_objective.png", "search_nodes.png",
                    "search_execution_time.png", "four_layout_distance.png", "four_layout_violations.png"]


# ------------------------------------------------------------------------------ CSP benchmark
def _cache_path(cache_dir, key):
    os.makedirs(cache_dir, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in key.replace("+", "p"))
    return os.path.join(cache_dir, safe + ".json")


def run_csp_case(products, slots, all_pairs, n, n_pairs, alg, protocol, cache_dir,
                 enforce_category=True, force=False, max_seconds=None):
    """One CSP run on the top-n products (by predicted demand) and the n_pairs strongest pairs with both
    endpoints inside the subset. With the strict aisle rule, a failed exact certificate short-circuits the
    run with status INFEASIBLE BY CERTIFICATE (no exhaustive search on a proven-infeasible problem)."""
    mode = "strict" if enforce_category else "relaxed"
    limit = max_seconds or MAX_SECONDS
    path = _cache_path(cache_dir, f"csp_{mode}_{protocol}_n{n}_p{n_pairs}_{alg}_t{int(limit)}")
    if os.path.exists(path) and not force:
        with open(path) as fh:
            return json.load(fh)
    sub = products[:n]
    ids = {p["id"] for p in sub}
    pairs = [x for x in all_pairs if x[0] in ids and x[1] in ids][:n_pairs]          # strongest first, endpoints inside subset
    assert all(a in ids and b in ids for a, b, *_ in pairs)
    cert = aisle_capacity_certificate(sub, slots)
    model = CSPModel(sub, slots, pairs, enforce_category=enforce_category)
    base = {"Products": n, "Algorithm": alg, "Protocol": protocol, "Mode": mode, "Pair constraints": model.n_pairs_used,
            "Aisle-rule certificate": "feasible" if cert["feasible"] else "INFEASIBLE", "Certificate detail": cert["detail"]}
    if enforce_category and not cert["feasible"]:
        row = {**base, "Status": INFEASIBLE_CERT, "Nodes": 0, "Backtracks": 0, "Constraint checks": 0, "Domain reductions": 0,
               "AC-3 revisions": 0, "Time (s)": 0.0, "Valid layout": "n/a", "pair_violations": None, "aisle_violations": None}
    else:
        res = ALGORITHMS[alg](model, max_nodes=MAX_NODES, max_seconds=limit)
        valid, pv, av = "n/a", None, None
        if res["layout"] is not None:
            rep = validate_layout(sub, res["layout"], slots, pairs)
            valid, pv, av = ("yes" if rep["valid"] else "no"), len(rep["pair_violations"]), len(rep["incompatible_aisle_violations"])
        row = {**base, "Status": res["status"], "Nodes": res["nodes"], "Backtracks": res["backtracks"],
               "Constraint checks": res["constraint_checks"], "Domain reductions": res["domain_reductions"],
               "AC-3 revisions": res["ac3_revisions"], "Time (s)": res["seconds"], "Valid layout": valid,
               "pair_violations": pv, "aisle_violations": av}
    with open(path, "w") as fh:
        json.dump(row, fh)
    return row


def run_csp_smoke(ctx, force=False, log=print):
    rows = [run_csp_case(ctx["products"], ctx["slots"], ctx["pairs"], 30, 10, a, "smoke (30 products, 10 pairs)", ctx["cache"], force=force)
            for a in ALGORITHMS]
    for r in rows:
        log(f"[SMOKE] {r['Algorithm']:11s} {r['Status']:20s} nodes={r['Nodes']} t={r['Time (s)']}s valid={r['Valid layout']}")
    return pd.DataFrame(rows)


def run_csp(ctx, force=False, log=print):
    """Strict comparison (protocols A and B) + one diagnostic at 120 products with ONLY the aisle rule relaxed."""
    rows = []
    for proto, sizes in PROTOCOLS.items():
        for n, k in sizes.items():
            for alg in ALGORITHMS:
                r = run_csp_case(ctx["products"], ctx["slots"], ctx["pairs"], n, k, alg, proto, ctx["cache"], force=force)
                log(f"[CSP] {proto[:1]} n={n:3d} pairs={r['Pair constraints']:2d} {alg:11s} -> {r['Status']:26s} nodes={r['Nodes']:>8} t={r['Time (s)']}s")
                rows.append(r)
    diag = []
    for alg in ALGORITHMS:
        r = run_csp_case(ctx["products"], ctx["slots"], ctx["pairs"], 120, 40, alg, DIAG_LABEL, ctx["cache"], enforce_category=False, force=force, max_seconds=DIAG_SECONDS)
        log(f"[DIAG] 120 products, aisle rule relaxed, {alg:11s} -> {r['Status']:20s} t={r['Time (s)']}s pair_viol={r['pair_violations']} aisle_viol={r['aisle_violations']}")
        diag.append(r)
    ctx["csp_df"], ctx["diag_df"] = pd.DataFrame(rows), pd.DataFrame(diag)
    ctx["csp_plot_df"] = pd.concat([ctx["csp_df"], ctx["diag_df"]], ignore_index=True)
    return ctx["csp_df"], ctx["diag_df"]


# ------------------------------------------------------------------------------ pipeline steps
def prepare(root):
    """Load + validate inputs, build warehouse, products, pair constraints, certificate, invoice split."""
    ctx = {"root": root}
    ctx["data"], ctx["data_report"] = load_data(os.path.join(root, "data"))
    ctx["slots"] = create_warehouse()
    ctx["sby"] = {s.slot_id: s for s in ctx["slots"]}
    ctx["products"] = build_products(ctx["data"]["forecasts"])
    ctx["pby"] = {p["id"]: p for p in ctx["products"]}
    ctx["pairs"] = build_pair_constraints(ctx["data"]["pairs"], [p["id"] for p in ctx["products"]])
    ctx["cert"] = aisle_capacity_certificate(ctx["products"], ctx["slots"])
    ctx["cert_counts"] = (sum(p["category"] == "cleaning" for p in ctx["products"]), sum(p["category"] in ("food", "fragile") for p in ctx["products"]))
    ctx["cache"] = os.path.join(root, "results", "experiments", "_cache")
    for d in ("results/layouts", "results/experiments", "results/validation", "figures/data", "reports"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    os.makedirs(ctx["cache"], exist_ok=True)
    inv = build_invoices(ctx["data"]["orders"])
    dev_ids, hold_ids = split_invoices(inv.keys(), DEV_INVOICES, SPLIT_SEED)
    ctx["dev_inv"] = {k: v for k, v in inv.items() if k in dev_ids}
    ctx["hold_inv"] = {k: v for k, v in inv.items() if k in hold_ids}
    ctx["objective"] = Objective(ctx["products"], ctx["slots"], ctx["pairs"])
    return ctx


def run_search(ctx):
    """Greedy / bounded UCS / A* from the NN-demand layout (objective uses predicted demand + training pairs only)."""
    P, S, pairs = ctx["products"], ctx["slots"], ctx["pairs"]
    nn = build_demand_layout(P, S, "demand")
    ctx["nn_layout"] = nn
    rows, res, lays = [], {}, {}
    for name, fn in SEARCH_RUNS.items():
        lay, info = fn(ctx["objective"], nn)
        rep = validate_layout(P, lay, S, pairs)
        res[name], lays[name] = info, lay
        rows.append({"Algorithm": name, **{k: v for k, v in info.items() if k != "swap_list"},
                     "final_hard_rules_ok": hard_basic_ok(rep), "final_fully_valid": rep["valid"],
                     "final_incompatible_aisle_pairs": len(rep["incompatible_aisle_violations"])})
    ctx["search_results"], ctx["search_layouts"], ctx["search_df"] = res, lays, pd.DataFrame(rows)
    return ctx["search_df"]


def build_layouts(ctx):
    """The four required layouts; NN + Swaps = simulated annealing on J from the NN layout (no test invoices)."""
    P, S = ctx["products"], ctx["slots"]
    ctx.setdefault("nn_layout", build_demand_layout(P, S, "demand"))
    sa_layout, sa_info = simulated_annealing(ctx["nn_layout"], ctx["objective"], iterations=SA_ITERATIONS, seed=SEED)
    ctx["sa_info"] = sa_info
    ctx["layouts"] = {"Random": build_random_layout(P, S, seed=SEED),
                      "Last-week demand": build_demand_layout(P, S, "last_week_demand"),
                      "NN demand": ctx["nn_layout"], "NN + Swaps": sa_layout}
    return ctx["layouts"], sa_info


def evaluate_layouts(ctx):
    """Four-layout table on the reserved holdout + the same layouts on development invoices (reporting only)."""
    def table(invoices):
        rows = []
        for name, lay in ctx["layouts"].items():
            rep = validate_layout(ctx["products"], lay, ctx["slots"], ctx["pairs"])
            m = evaluate_layout(lay, ctx["slots"], invoices)
            rows.append({"Layout": name, "Invoices evaluated": m["invoices_evaluated"], "Product-line coverage (%)": m["product_line_coverage_pct"],
                         "Total picker distance": m["total_picker_distance"], "Average distance per invoice": m["avg_distance_per_invoice"],
                         "Pair violations": len(rep["pair_violations"]), "Total excess distance": rep["total_excess_distance"],
                         "Incompatible aisle pairs": len(rep["incompatible_aisle_violations"]),
                         "Basic rules OK (slots/capacity/heavy)": hard_basic_ok(rep), "Strictly valid (all hard constraints)": rep["valid"]})
        df = pd.DataFrame(rows)
        ref = df.set_index("Layout")["Average distance per invoice"]
        df["Improvement vs Random (%)"] = ((ref["Random"] - df["Average distance per invoice"]) / ref["Random"] * 100).round(2)
        df["Improvement vs NN demand (%)"] = ((ref["NN demand"] - df["Average distance per invoice"]) / ref["NN demand"] * 100).round(2)
        return df
    ctx["four_df"] = table(ctx["hold_inv"])
    ctx["dev_df"] = table(ctx["dev_inv"])
    return ctx["four_df"], ctx["dev_df"]


def export_layouts(ctx):
    root, sby, pby = ctx["root"], ctx["sby"], ctx["pby"]
    for name, fname in LAYOUT_FILES.items():
        rows = [{"product_id": pid, "slot_id": sid, "row": sby[sid].row, "col": sby[sid].col, "aisle": sby[sid].aisle + 1,
                 "level": sby[sid].level, "category": pby[pid]["category"], "heavy": pby[pid]["heavy"],
                 "required_capacity": pby[pid]["required_capacity"], "predicted_demand": pby[pid]["demand"],
                 "last_week_demand": pby[pid]["last_week_demand"]} for pid, sid in ctx["layouts"][name].items()]
        pd.DataFrame(rows).sort_values("slot_id").to_csv(os.path.join(root, "results/layouts", fname + ".csv"), index=False)
    pv, summ = [], []
    strength = {(a, b): s for a, b, d, s in ctx["pairs"]}
    for name, lay in ctx["layouts"].items():
        rep = validate_layout(ctx["products"], lay, ctx["slots"], ctx["pairs"])
        summ.append({"layout": name, **report_summary(rep)})
        for a, b, dist, dmax in rep["pair_violations"]:
            pv.append({"layout": name, "product_a": a, "product_b": b, "strength": strength[(a, b)], "distance": dist,
                       "max_distance": dmax, "excess": dist - dmax, "category_a": pby[a]["category"], "category_b": pby[b]["category"]})
    pd.DataFrame(pv).to_csv(os.path.join(root, "results/validation/remaining_pair_violations.csv"), index=False)
    ctx["layout_val"] = pd.DataFrame(summ)
    ctx["layout_val"].to_csv(os.path.join(root, "results/validation/layout_validation_summary.csv"), index=False)
    ctx["csp_df"].to_csv(os.path.join(root, "results/experiments/csp_comparison.csv"), index=False)
    ctx["diag_df"].to_csv(os.path.join(root, "results/experiments/csp_diagnostic_relaxed_aisle_rule.csv"), index=False)
    ctx["search_df"].to_csv(os.path.join(root, "results/experiments/search_comparison.csv"), index=False)
    ctx["four_df"].to_csv(os.path.join(root, "results/experiments/four_layout_comparison.csv"), index=False)
    ctx["dev_df"].to_csv(os.path.join(root, "results/experiments/four_layout_development_invoices.csv"), index=False)
    pd.DataFrame([{"Layout": "Initial", "Average distance": 29.344, "Pair violations": 121, "source": "HISTORICAL reference (earlier notebook), not recomputed"},
                  {"Layout": "Joint optimization", "Average distance": 27.006, "Pair violations": 22, "source": "HISTORICAL reference (earlier notebook), not recomputed"}]
                 ).to_csv(os.path.join(root, "results/experiments/historical_reference.csv"), index=False)


def make_figures(ctx):
    from . import visualization as V
    root = ctx["root"]
    F, FD = os.path.join(root, "figures"), os.path.join(root, "figures", "data")
    P, S, pairs, L = ctx["products"], ctx["slots"], ctx["pairs"], ctx["layouts"]
    V.fig_warehouse_layout(P, L["NN + Swaps"], S, pairs, f"{F}/warehouse_layout.png", FD)
    V.fig_copurchase_network(P, pairs, L["NN + Swaps"], S, f"{F}/copurchase_network.png", FD)
    cp = pd.DataFrame(pairs, columns=["product_a", "product_b", "max_distance", "strength"])
    cp["category_a"], cp["category_b"] = cp.product_a.map(lambda i: ctx["pby"][i]["category"]), cp.product_b.map(lambda i: ctx["pby"][i]["category"])
    cp.to_csv(f"{FD}/copurchase_pairs_all.csv", index=False)
    V.fig_demand_distribution(P, L, S, f"{F}/demand_distribution.png", FD)
    V.fig_csp_time(ctx["csp_plot_df"], f"{F}/csp_execution_time.png", FD)
    V.fig_csp_nodes(ctx["csp_plot_df"], f"{F}/csp_search_nodes.png", FD)
    V.fig_csp_backtracks(ctx["csp_plot_df"], f"{F}/csp_backtracks.png", FD)
    V.fig_search_all(ctx["search_df"], F, FD)
    V.fig_four_layouts(ctx["four_df"], F, FD)


def run_qa_step(ctx):
    from .qa import run_qa
    ctx["qa_df"] = run_qa(ctx, ctx["root"])
    ctx["qa_df"].to_csv(os.path.join(ctx["root"], "results/validation/final_qa_report.csv"), index=False)
    return ctx["qa_df"]


def write_all_reports(ctx):
    from .reporting import write_reports
    write_reports(ctx["root"], ctx)


def run_complete_project(root, force=False, log=print):
    """Load -> validate -> warehouse/products/constraints -> CSP -> Search -> layouts -> picker evaluation
    -> figures -> QA -> exports -> reports. CSP results are cached (resume after interruption)."""
    log("1/10 loading and validating inputs"); ctx = prepare(root)
    log(f"    certificate (aisle rule, 120 products): {ctx['cert']}")
    log("2/10 CSP smoke test + comparison"); run_csp_smoke(ctx, force, log); run_csp(ctx, force, log)
    log("3/10 search experiments"); run_search(ctx)
    log("4/10 layouts (NN + Swaps via SA)"); build_layouts(ctx)
    log("5/10 picker evaluation on held-out invoices"); evaluate_layouts(ctx)
    log("6/10 exporting layouts/tables"); export_layouts(ctx)
    log("7/10 figures"); make_figures(ctx)
    log("8/10 QA + unit tests"); run_qa_step(ctx)
    log("9/10 reports"); write_all_reports(ctx)
    log("10/10 done")
    return ctx
