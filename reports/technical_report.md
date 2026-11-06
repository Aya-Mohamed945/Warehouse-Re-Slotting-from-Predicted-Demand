# Technical report - P8 Warehouse Re-Slotting from Predicted Demand (Person 2)

## 1. Objective
Place 120 products in a 120-slot warehouse to reduce picker walking distance, using predicted next-week demand, products bought together, capacity, heavy/low-shelf rules and category/aisle compatibility. Final quality is measured on real held-out invoices.

## 2. Dataset inputs
`forecasts.csv` (product_id, predicted_demand, last_week_demand; 120 products), `copurchase_pairs.csv` (200 pairs, 63 products; strength kept as float), `test_orders.csv` (27881 unique lines, 5846 invoices; invoice column detected as `Invoice`; no quantity column). Validation counts: see `experiment_results.md` section 1.

## 3. Warehouse design (simulated)
10 x 12 grid, slot id = row*12+col, Depot (0,0), Manhattan distance, rows 0-3 low / 4-6 middle / 7-9 high, aisle = col // 3 (4 aisles x 30 slots), capacity 100 per slot.

## 4. Simulated assumptions / 5. Product attributes
Category (food, cleaning, stationery, fragile), heavy flag (~15 %) and required capacity (1-80) are drawn with seed 42 (same draw order as the original notebook). Category rules: cleaning-food and cleaning-fragile incompatible (must not share an aisle); all other pairs, and same-category pairs, compatible. These are business assumptions, not dataset facts.

## 6. Constraint formulation
Variables = products; domains = slots (bit masks, bit 0 = slot nearest the Depot). Unary: capacity, heavy -> low shelf. Global: one product per slot. Binary: co-purchase Manhattan distance <= max_distance (HARD in the CSP and in strict validation, SOFT in search/optimisation); incompatible categories not in one aisle. One validator (`validate_layout`) is used everywhere.
**Feasibility:** the aisle rule alone needs whole aisles free of food/fragile for cleaning products. With 31 cleaning and 61 food+fragile products, no split of 4x30 slots holds both (31 cleaning products need whole aisles free of food/fragile, 61 food+fragile products need the remaining aisles; no split of 4 aisles ([30, 30, 30, 30] slots) holds both (best slack A/B = (-1, 29))). The conflicting assumption is "4 aisles of 30 slots + the simulated category counts + cleaning/food/fragile incompatibility". The strict rule is preserved; a relaxed-rule diagnostic is reported separately. No input data and no rule were changed.

## 7. CSP algorithms
* BT - static demand order, Depot-nearest value order, candidate checked against assigned variables, pair index (no scan of all pairs).
* BT+FC - MRV (degree tie-break), incremental forward checking (alldifferent, distance balls, aisle masks), trail-based domain restoration, plus a Hall-type pigeonhole check for heavy products.
* BT+FC+AC-3 - FC plus real AC-3 over pair-distance arcs and incompatible-category arcs (queue, revise by support, neighbour re-queue, empty-domain detection, revision/check counters). The alldifferent constraint is enforced by FC, not by n^2 binary arcs (documented trade-off).
Statuses: SOLVED, NO SOLUTION, NODE LIMIT REACHED, TIME LIMIT REACHED, INFEASIBLE BY CERTIFICATE.

## 8. Search algorithms
State = complete layout; action = swap two products' slots (one of the 30 highest-demand products with a partner in the 40 slots nearest the Depot, or another top-30 product); cost 1 per swap; depth <= 6; 300-expansion budget; duplicates pruned by layout signature. Greedy: priority J. Bounded UCS: priority g (J breaks ties). A* variant: f = g + h with h = (J - target) / best single-swap gain at the root - not admissible, so optimality is not claimed. Goal: J <= 90 % of the initial J. Every child keeps unique slots, capacity, heavy->low and never adds incompatible-aisle pairs.

## 9. Optimisation objective
J = WWD + 0.04 x pair_excess; WWD = sum(predicted demand x distance to Depot)/sum(demand); pair_excess = sum(max(0, distance - max_distance)). Lambda 0.04 = the original per-invoice weight 0.2 / ~4.8 lines per invoice. NN + Swaps = swap-based simulated annealing on J from the NN layout (100,000 proposals, seed 42), hard rules enforced on every move. It uses no test invoices.

## 10. Picker-distance simulation
Depot -> nearest unvisited product (Manhattan, deterministic tie-break) -> ... -> Depot, one visit per distinct product per invoice. A nearest-neighbour heuristic, not an optimal TSP tour. Same model for all layouts; development invoices (1,000, seed 2026 split) are excluded from the holdout.

## 11. Four-layout comparison (holdout, average picker distance)
Random 33.150; Last-week 28.963; NN demand 29.028; NN + Swaps 27.577
(16.81 % better than Random, 5.00 % better than NN demand). Pair violations: Random 156, Last-week demand 123, NN demand 139, NN + Swaps 37. Incompatible aisle pairs: Random 452, Last-week demand 448, NN demand 473, NN + Swaps 2. No layout is strictly valid. See `figures/four_layout_distance.png`, `figures/four_layout_violations.png`.

## 12. Experimental results
CSP: BT+FC solved 4, BT+FC+AC-3 solved 4, BT solved 0 of the strict runs; 120-product strict runs are INFEASIBLE BY CERTIFICATE. Figures: `csp_execution_time.png`, `csp_search_nodes.png`, `csp_backtracks.png`. Search: `search_objective.png`, `search_nodes.png`, `search_execution_time.png`. Tables: `experiment_results.md`.

## 13. Validation
{'PASS': 21, 'FAIL': 2, 'NOT VERIFIABLE': 1} (see `results/validation/final_qa_report.csv`; 39+ unit tests in `tests/`).

## 14. Limitations
See `assumptions_and_limitations.md`.
