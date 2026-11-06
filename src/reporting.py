"""Writes the three markdown reports from the REAL result tables (no hand-typed results)."""
import os


def md_table(df, floatfmt="{:,.4g}"):
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "|".join("---" for _ in df.columns) + "|\n"
    body = "".join("| " + " | ".join(floatfmt.format(v) if isinstance(v, float) else str(v) for v in r) + " |\n" for _, r in df.iterrows())
    return head + body


def write_reports(root, ctx):
    rep = os.path.join(root, "reports")
    os.makedirs(rep, exist_ok=True)
    csp, diag, srch, four, dev, qa = ctx["csp_df"], ctx["diag_df"], ctx["search_df"], ctx["four_df"], ctx["dev_df"], ctx["qa_df"]
    cert, dr, lam, sa = ctx["cert"], ctx["data_report"], ctx["objective"].lam, ctx["sa_info"]
    f = four.set_index("Layout")
    ncl, nfb = ctx["cert_counts"]
    csp_cols = ["Products", "Algorithm", "Protocol", "Pair constraints", "Status", "Nodes", "Backtracks", "Constraint checks",
                "Domain reductions", "AC-3 revisions", "Time (s)", "Valid layout"]
    srch_cols = ["Algorithm", "initial_objective", "final_objective", "target_objective", "initial_wwd", "final_wwd", "initial_pair_violations",
                 "final_pair_violations", "swaps", "expanded_nodes", "generated_nodes", "seconds", "target_reached", "final_hard_rules_ok"]
    four_cols = ["Layout", "Invoices evaluated", "Product-line coverage (%)", "Total picker distance", "Average distance per invoice", "Pair violations",
                 "Total excess distance", "Incompatible aisle pairs", "Improvement vs Random (%)", "Improvement vs NN demand (%)",
                 "Basic rules OK (slots/capacity/heavy)", "Strictly valid (all hard constraints)"]
    strict = csp
    solved = strict[strict.Status == "SOLVED"].groupby("Algorithm").size().to_dict()
    diag_txt = "; ".join(f"{r['Algorithm']}: {r['Status']} ({r['Time (s)']} s)" for _, r in diag.iterrows())

    results = f"""# Experiment results

All numbers were produced by the final run of `notebook/P8_Warehouse_Person2_Final.ipynb` (or `run_complete_project`). Historical values are only in `results/experiments/historical_reference.csv`, labelled as historical.

## 1. Input validation
{dr}

## 2. Feasibility certificate (strict aisle rule, all 120 products)
{ncl} cleaning and {nfb} food+fragile products; 4 aisles x 30 slots. **Feasible: {cert['feasible']}.** {cert['detail']}.

## 3. CSP comparison (strict rules; limit 20 s / 2,000,000 nodes per run)
Protocol A = 20/30/40 strongest pairs at 60/90/120 products; protocol B = 30 strongest pairs at each size.
Status `INFEASIBLE BY CERTIFICATE` = exact counting certificate failed, no search was run. `TIME LIMIT REACHED` is never evidence of infeasibility.

{md_table(csp[csp_cols])}
Solved runs per algorithm: {solved}.

### Diagnostic only (120 products, 40 pairs, aisle rule RELAXED, everything else strict; limit 45 s because this instance is borderline at 20 s)
{md_table(diag[csp_cols + ['pair_violations', 'aisle_violations']])}
Results: {diag_txt}. A layout produced here is *not* strictly valid because the relaxed aisle rule leaves incompatible pairs in the same aisle; it shows the remaining constraints (capacity, heavy, 40 pair distances) can be met together.

## 4. Search comparison (start NN demand, J = WWD + {lam} x pair excess, depth <= 6, 300 expansions)
{md_table(srch[srch_cols])}
## 5. Four-layout comparison on the reserved holdout ({int(four['Invoices evaluated'].iloc[0])} invoices)
{md_table(four[four_cols])}
Same layouts on the {int(dev['Invoices evaluated'].iloc[0])} development invoices (reporting only, never used for tuning): see `results/experiments/four_layout_development_invoices.csv`.

NN + Swaps optimiser run: {sa}.

Historical reference (earlier notebook, not recomputed here): initial 29.344 average distance / 121 violations; joint optimisation 27.006 / 22 violations.

## 6. QA and unit tests
{md_table(qa)}
## Figures
`figures/`: warehouse_layout, copurchase_network, demand_distribution, csp_execution_time, csp_search_nodes, csp_backtracks, search_objective, search_nodes, search_execution_time, four_layout_distance, four_layout_violations (each with `figures/data/<name>_data.csv`).
"""
    open(os.path.join(rep, "experiment_results.md"), "w").write(results)

    tech = f"""# Technical report - P8 Warehouse Re-Slotting from Predicted Demand (Person 2)

## 1. Objective
Place 120 products in a 120-slot warehouse to reduce picker walking distance, using predicted next-week demand, products bought together, capacity, heavy/low-shelf rules and category/aisle compatibility. Final quality is measured on real held-out invoices.

## 2. Dataset inputs
`forecasts.csv` (product_id, predicted_demand, last_week_demand; {dr['forecast_rows']} products), `copurchase_pairs.csv` ({dr['pair_rows']} pairs, {dr['pair_unique_products']} products; strength kept as float), `test_orders.csv` ({dr['order_lines']} unique lines, {dr['order_invoices']} invoices; invoice column detected as `{dr['order_invoice_column_detected']}`; no quantity column). Validation counts: see `experiment_results.md` section 1.

## 3. Warehouse design (simulated)
10 x 12 grid, slot id = row*12+col, Depot (0,0), Manhattan distance, rows 0-3 low / 4-6 middle / 7-9 high, aisle = col // 3 (4 aisles x 30 slots), capacity 100 per slot.

## 4. Simulated assumptions / 5. Product attributes
Category (food, cleaning, stationery, fragile), heavy flag (~15 %) and required capacity (1-80) are drawn with seed 42 (same draw order as the original notebook). Category rules: cleaning-food and cleaning-fragile incompatible (must not share an aisle); all other pairs, and same-category pairs, compatible. These are business assumptions, not dataset facts.

## 6. Constraint formulation
Variables = products; domains = slots (bit masks, bit 0 = slot nearest the Depot). Unary: capacity, heavy -> low shelf. Global: one product per slot. Binary: co-purchase Manhattan distance <= max_distance (HARD in the CSP and in strict validation, SOFT in search/optimisation); incompatible categories not in one aisle. One validator (`validate_layout`) is used everywhere.
**Feasibility:** the aisle rule alone needs whole aisles free of food/fragile for cleaning products. With {ncl} cleaning and {nfb} food+fragile products, no split of 4x30 slots holds both ({cert['detail']}). The conflicting assumption is "4 aisles of 30 slots + the simulated category counts + cleaning/food/fragile incompatibility". The strict rule is preserved; a relaxed-rule diagnostic is reported separately. No input data and no rule were changed.

## 7. CSP algorithms
* BT - static demand order, Depot-nearest value order, candidate checked against assigned variables, pair index (no scan of all pairs).
* BT+FC - MRV (degree tie-break), incremental forward checking (alldifferent, distance balls, aisle masks), trail-based domain restoration, plus a Hall-type pigeonhole check for heavy products.
* BT+FC+AC-3 - FC plus real AC-3 over pair-distance arcs and incompatible-category arcs (queue, revise by support, neighbour re-queue, empty-domain detection, revision/check counters). The alldifferent constraint is enforced by FC, not by n^2 binary arcs (documented trade-off).
Statuses: SOLVED, NO SOLUTION, NODE LIMIT REACHED, TIME LIMIT REACHED, INFEASIBLE BY CERTIFICATE.

## 8. Search algorithms
State = complete layout; action = swap two products' slots (one of the 30 highest-demand products with a partner in the 40 slots nearest the Depot, or another top-30 product); cost 1 per swap; depth <= 6; 300-expansion budget; duplicates pruned by layout signature. Greedy: priority J. Bounded UCS: priority g (J breaks ties). A* variant: f = g + h with h = (J - target) / best single-swap gain at the root - not admissible, so optimality is not claimed. Goal: J <= 90 % of the initial J. Every child keeps unique slots, capacity, heavy->low and never adds incompatible-aisle pairs.

## 9. Optimisation objective
J = WWD + {lam} x pair_excess; WWD = sum(predicted demand x distance to Depot)/sum(demand); pair_excess = sum(max(0, distance - max_distance)). Lambda 0.04 = the original per-invoice weight 0.2 / ~4.8 lines per invoice. NN + Swaps = swap-based simulated annealing on J from the NN layout (100,000 proposals, seed 42), hard rules enforced on every move. It uses no test invoices.

## 10. Picker-distance simulation
Depot -> nearest unvisited product (Manhattan, deterministic tie-break) -> ... -> Depot, one visit per distinct product per invoice. A nearest-neighbour heuristic, not an optimal TSP tour. Same model for all layouts; development invoices (1,000, seed 2026 split) are excluded from the holdout.

## 11. Four-layout comparison (holdout, average picker distance)
Random {f.loc['Random','Average distance per invoice']:.3f}; Last-week {f.loc['Last-week demand','Average distance per invoice']:.3f}; NN demand {f.loc['NN demand','Average distance per invoice']:.3f}; NN + Swaps {f.loc['NN + Swaps','Average distance per invoice']:.3f}
({f.loc['NN + Swaps','Improvement vs Random (%)']:.2f} % better than Random, {f.loc['NN + Swaps','Improvement vs NN demand (%)']:.2f} % better than NN demand). Pair violations: {', '.join(f"{k} {int(v)}" for k, v in f['Pair violations'].items())}. Incompatible aisle pairs: {', '.join(f"{k} {int(v)}" for k, v in f['Incompatible aisle pairs'].items())}. No layout is strictly valid. See `figures/four_layout_distance.png`, `figures/four_layout_violations.png`.

## 12. Experimental results
CSP: BT+FC solved {solved.get('BT+FC', 0)}, BT+FC+AC-3 solved {solved.get('BT+FC+AC-3', 0)}, BT solved {solved.get('BT', 0)} of the strict runs; 120-product strict runs are INFEASIBLE BY CERTIFICATE. Figures: `csp_execution_time.png`, `csp_search_nodes.png`, `csp_backtracks.png`. Search: `search_objective.png`, `search_nodes.png`, `search_execution_time.png`. Tables: `experiment_results.md`.

## 13. Validation
{qa.Result.value_counts().to_dict()} (see `results/validation/final_qa_report.csv`; 39+ unit tests in `tests/`).

## 14. Limitations
See `assumptions_and_limitations.md`.
"""
    open(os.path.join(rep, "technical_report.md"), "w").write(tech)

    lim = f"""# Assumptions and limitations

## Simulated assumptions (not from the UCI data)
Warehouse geometry, shelf levels, aisles, capacity 100, product category / heavy flag / required capacity (seed 42), and the category-compatibility table. Co-purchase `strength` and `max_distance` come from Person 1's pair file.

## Limitations that cannot honestly be resolved
1. **Strict 120-product problem is infeasible** ({cert['detail']}). No full layout can satisfy the aisle rule; each layout reports its incompatible-aisle pairs. Making it feasible needs a changed *assumption* (e.g. 6 aisles x 20 slots or different category mix); this was deliberately not done silently. Effect: the strict experiment at 120 products is a certificate, not a search result.
2. **Pair constraints are soft in search/optimisation**; no full layout meets all of them (remaining violations in `results/validation/remaining_pair_violations.csv`).
3. Plain BT times out even on small strict instances (static order thrashes under the pair constraints); a limit is not a proof.
4. Time limits (20 s strict runs, 45 s for the relaxed diagnostic) and runtimes are machine dependent; the relaxed 120-product diagnostic is close to the limit for BT+FC (it solved in ~14 s in one run and exceeded 20 s in another).
5. A* heuristic is inadmissible: no optimality claim. Search results are single deterministic runs with a 300-expansion budget.
6. Picker route is a nearest-neighbour heuristic; no aisle blocking; one pick per distinct product (no quantities in the data).
7. Capacity never binds (slot 100 vs needs <= 80, one product per slot). Heavy items must use low rows, which are also the rows nearest the Depot.
8. Training/test leakage inside Person 1's files cannot be verified (their training window was not supplied); QA marks it NOT VERIFIABLE. The final optimiser uses no test invoices.
9. Historical numbers (29.344 -> 27.006, 121 -> 22 violations) are not reproduced; the earlier run is not available and its simulator broke route ties by Python set order.

## Simplifications made (Category C removed, Category B kept only if cheap)
| Item | Decision | Why |
|---|---|---|
| Legacy dev-invoice-tuned optimiser | removed | redundant with SA, tuned on test-file invoices |
| dom/deg variable-order option | removed | worse than MRV in tests |
| 34-product "core-only" diagnostic | removed | overlaps with the relaxed-aisle diagnostic |
| Figures: CSP success rate, search swaps, search walking distance, four-layout improvement | removed | redundant; improvement % is in the table |
| Reproduced-vs-historical joins, historical dev comparison tables | reduced to one labelled historical reference file | avoid presenting historical numbers as reproduced |
| Protocol B (30 pairs) | kept | cheap, matches the AC-3 setting in the proposal |
| Hall pigeonhole check for heavy products | kept | small, documented, helps FC/AC-3 |
| Result cache (`_cache`) | kept (one JSON per CSP run) | lets interrupted runs resume |
"""
    open(os.path.join(rep, "assumptions_and_limitations.md"), "w").write(lim)
