# Experiment results

All numbers were produced by the final run of `notebook/P8_Warehouse_Person2_Final.ipynb` (or `run_complete_project`). Historical values are only in `results/experiments/historical_reference.csv`, labelled as historical.

## 1. Input validation
{'forecast_rows_raw': 120, 'pair_rows_raw': 200, 'order_rows_raw': 27881, 'order_invoice_column_detected': 'Invoice', 'order_product_column_detected': 'StockCode', 'forecast_rows_dropped_invalid': 0, 'forecast_duplicate_ids_dropped': 0, 'forecast_last_week_missing_filled_with_0': 0, 'pair_rows_dropped_invalid': 0, 'pair_rows_dropped_unknown_product': 0, 'pair_duplicates_dropped': 0, 'order_lines_dropped_missing_id': 0, 'order_duplicate_lines_dropped': 0, 'order_products_not_in_forecasts': 0, 'forecast_rows': 120, 'pair_rows': 200, 'pair_unique_products': 63, 'order_lines': 27881, 'order_invoices': 5846, 'order_has_quantity_column': False}

## 2. Feasibility certificate (strict aisle rule, all 120 products)
31 cleaning and 61 food+fragile products; 4 aisles x 30 slots. **Feasible: False.** 31 cleaning products need whole aisles free of food/fragile, 61 food+fragile products need the remaining aisles; no split of 4 aisles ([30, 30, 30, 30] slots) holds both (best slack A/B = (-1, 29)).

## 3. CSP comparison (strict rules; limit 20 s / 2,000,000 nodes per run)
Protocol A = 20/30/40 strongest pairs at 60/90/120 products; protocol B = 30 strongest pairs at each size.
Status `INFEASIBLE BY CERTIFICATE` = exact counting certificate failed, no search was run. `TIME LIMIT REACHED` is never evidence of infeasibility.

| Products | Algorithm | Protocol | Pair constraints | Status | Nodes | Backtracks | Constraint checks | Domain reductions | AC-3 revisions | Time (s) | Valid layout |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | BT | A (20/30/40 strongest pairs) | 20 | TIME LIMIT REACHED | 162500 | 162499 | 37409240 | 0 | 0 | 20 | n/a |
| 60 | BT+FC | A (20/30/40 strongest pairs) | 20 | SOLVED | 64 | 9 | 2650 | 6841 | 0 | 0.0019 | yes |
| 60 | BT+FC+AC-3 | A (20/30/40 strongest pairs) | 20 | SOLVED | 63 | 7 | 89574 | 7194 | 16933 | 0.0275 | yes |
| 90 | BT | A (20/30/40 strongest pairs) | 30 | TIME LIMIT REACHED | 185374 | 185373 | 42497984 | 0 | 0 | 20 | n/a |
| 90 | BT+FC | A (20/30/40 strongest pairs) | 30 | SOLVED | 106 | 27 | 7428 | 14234 | 0 | 0.0041 | yes |
| 90 | BT+FC+AC-3 | A (20/30/40 strongest pairs) | 30 | SOLVED | 106 | 26 | 311645 | 11254 | 68242 | 0.1043 | yes |
| 120 | BT | A (20/30/40 strongest pairs) | 40 | INFEASIBLE BY CERTIFICATE | 0 | 0 | 0 | 0 | 0 | 0 | n/a |
| 120 | BT+FC | A (20/30/40 strongest pairs) | 40 | INFEASIBLE BY CERTIFICATE | 0 | 0 | 0 | 0 | 0 | 0 | n/a |
| 120 | BT+FC+AC-3 | A (20/30/40 strongest pairs) | 40 | INFEASIBLE BY CERTIFICATE | 0 | 0 | 0 | 0 | 0 | 0 | n/a |
| 60 | BT | B (30 strongest pairs) | 30 | TIME LIMIT REACHED | 196083 | 196082 | 43090959 | 0 | 0 | 20 | n/a |
| 60 | BT+FC | B (30 strongest pairs) | 30 | SOLVED | 708 | 948 | 52445 | 106754 | 0 | 0.0242 | yes |
| 60 | BT+FC+AC-3 | B (30 strongest pairs) | 30 | SOLVED | 895 | 1137 | 1602808 | 135423 | 363006 | 0.6041 | yes |
| 90 | BT | B (30 strongest pairs) | 30 | TIME LIMIT REACHED | 176909 | 176908 | 40591420 | 0 | 0 | 20 | n/a |
| 90 | BT+FC | B (30 strongest pairs) | 30 | SOLVED | 106 | 27 | 7428 | 14234 | 0 | 0.0086 | yes |
| 90 | BT+FC+AC-3 | B (30 strongest pairs) | 30 | SOLVED | 106 | 26 | 311645 | 11254 | 68242 | 0.1375 | yes |
| 120 | BT | B (30 strongest pairs) | 30 | INFEASIBLE BY CERTIFICATE | 0 | 0 | 0 | 0 | 0 | 0 | n/a |
| 120 | BT+FC | B (30 strongest pairs) | 30 | INFEASIBLE BY CERTIFICATE | 0 | 0 | 0 | 0 | 0 | 0 | n/a |
| 120 | BT+FC+AC-3 | B (30 strongest pairs) | 30 | INFEASIBLE BY CERTIFICATE | 0 | 0 | 0 | 0 | 0 | 0 | n/a |

Solved runs per algorithm: {'BT+FC': 4, 'BT+FC+AC-3': 4}.

### Diagnostic only (120 products, 40 pairs, aisle rule RELAXED, everything else strict; limit 45 s because this instance is borderline at 20 s)
| Products | Algorithm | Protocol | Pair constraints | Status | Nodes | Backtracks | Constraint checks | Domain reductions | AC-3 revisions | Time (s) | Valid layout | pair_violations | aisle_violations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | BT | Diagnostic: 120 products, aisle rule RELAXED | 40 | TIME LIMIT REACHED | 335547 | 335546 | 73632068 | 0 | 0 | 45 | n/a | nan | nan |
| 120 | BT+FC | Diagnostic: 120 products, aisle rule RELAXED | 40 | SOLVED | 244698 | 375050 | 31265342 | 41188007 | 0 | 25.16 | no | 0 | 474 |
| 120 | BT+FC+AC-3 | Diagnostic: 120 products, aisle rule RELAXED | 40 | TIME LIMIT REACHED | 116240 | 179641 | 97763352 | 15167422 | 3062034 | 45 | n/a | nan | nan |

Results: BT: TIME LIMIT REACHED (45.0001 s); BT+FC: SOLVED (25.1562 s); BT+FC+AC-3: TIME LIMIT REACHED (45.0001 s). A layout produced here is *not* strictly valid because the relaxed aisle rule leaves incompatible pairs in the same aisle; it shows the remaining constraints (capacity, heavy, 40 pair distances) can be met together.

## 4. Search comparison (start NN demand, J = WWD + 0.04 x pair excess, depth <= 6, 300 expansions)
| Algorithm | initial_objective | final_objective | target_objective | initial_wwd | final_wwd | initial_pair_violations | final_pair_violations | swaps | expanded_nodes | generated_nodes | seconds | target_reached | final_hard_rules_ok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Greedy Best-First | 32.38 | 28.47 | 29.14 | 6.736 | 6.75 | 139 | 124 | 2 | 2 | 993 | 0.013 | True | True |
| Bounded UCS | 32.38 | 28.42 | 29.14 | 6.736 | 6.74 | 139 | 124 | 2 | 300 | 103106 | 2.127 | True | True |
| A* variant | 32.38 | 28.42 | 29.14 | 6.736 | 6.74 | 139 | 124 | 2 | 52 | 23921 | 0.312 | True | True |

## 5. Four-layout comparison on the reserved holdout (4846 invoices)
| Layout | Invoices evaluated | Product-line coverage (%) | Total picker distance | Average distance per invoice | Pair violations | Total excess distance | Incompatible aisle pairs | Improvement vs Random (%) | Improvement vs NN demand (%) | Basic rules OK (slots/capacity/heavy) | Strictly valid (all hard constraints) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Random | 4846 | 100 | 160646 | 33.15 | 156 | 857 | 452 | 0 | -14.2 | True | False |
| Last-week demand | 4846 | 100 | 140356 | 28.96 | 123 | 539 | 448 | 12.63 | 0.22 | True | False |
| NN demand | 4846 | 100 | 140668 | 29.03 | 139 | 641 | 473 | 12.43 | 0 | True | False |
| NN + Swaps | 4846 | 100 | 133640 | 27.58 | 37 | 65 | 2 | 16.81 | 5 | True | False |

Same layouts on the 1000 development invoices (reporting only, never used for tuning): see `results/experiments/four_layout_development_invoices.csv`.

NN + Swaps optimiser run: {'iterations': 100000, 'accepted_moves': 7812, 'rejected_hard_constraint': 66198, 'initial_objective': 32.3756, 'final_objective': 8.7284, 'final_wwd': 6.1284, 'final_pair_violations': 37, 'final_total_excess': 65, 'seconds': 0.45}.

Historical reference (earlier notebook, not recomputed here): initial 29.344 average distance / 121 violations; joint optimisation 27.006 / 22 violations.

## 6. QA and unit tests
| Test | Scope | Result | Details |
|---|---|---|---|
| Product assignment (all 120 assigned, none missing) - 4 layouts | basic | PASS | {'Random': 120, 'Last-week demand': 120, 'NN demand': 120, 'NN + Swaps': 120} |
| Unique slots (120 distinct valid slots) - 4 layouts | basic | PASS | no duplicate or unknown slot ids |
| Capacity | basic | PASS | 0 violations in all four layouts (NB: every slot has capacity 100 and needs are 1-80, so the rule never binds) |
| Heavy products on low shelves | basic | PASS | 0 violations in all four layouts |
| Category compatibility function (symmetric, matches specified table) | integration | PASS | 10 unordered pairs + 4 same-category cases checked |
| Category-aisle rule on the 4 full 120-product layouts | strict | FAIL | incompatible same-aisle product pairs: {'Random': 452, 'Last-week demand': 448, 'NN demand': 473, 'NN + Swaps': 2}. Counting certificate says a violation-free 120-layout is IMPOSSIBLE: 31 cleaning products need whole aisles free of food/fragile, 61 food+fragile products need the remaining aisles; no split of 4 aisles ([30, 30, 30, 30] slots) holds both (best slack A/B = (-1, 29)) |
| CSP-solved layouts (strict rules, 60/90 products) satisfy ALL hard constraints | integration | PASS | 8 solved runs, all validated with validate_layout (incl. hard pair distances and aisle rule) |
| INFEASIBLE BY CERTIFICATE status appears exactly where the exact certificate fails | strict | PASS | certificate feasible? {60: True, 90: True, 120: False}; rows marked infeasible: [120] |
| Certificate inputs recomputed from the real data | integration | PASS | cleaning=31, food+fragile=61, aisles=[0, 1, 2, 3] x 30 slots; strict 120-product layout feasible = False |
| Layouts reported 'valid' really are valid | integration | PASS | {'Random': False, 'Last-week demand': False, 'NN demand': False, 'NN + Swaps': False} |
| Hard co-purchase constraints satisfied on the 4 full layouts | strict | FAIL | pair violations remaining (soft objective, reported separately): {'Random': 156, 'Last-week demand': 123, 'NN demand': 139, 'NN + Swaps': 37} |
| Search validity (every swap keeps unique slot/capacity/heavy and does not add aisle conflicts) | integration | PASS | Greedy Best-First: 2 swaps replayed; Bounded UCS: 2 swaps replayed; A* variant: 2 swaps replayed |
| All four layouts use the same product set | integration | PASS | 120 products |
| Test-order evaluation: same invoices, same simulator for all 4 layouts | integration | PASS | 4846 invoices each; coverage [100.0]% |
| Four-layout table reproduces from a fresh evaluation | integration | PASS | recomputed average distances equal the exported table |
| No duplicated (invoice, product) lines counted | integration | PASS | 27881 unique lines, 5846 invoices |
| Development / holdout invoices disjoint and exhaustive | integration | PASS | 1000 dev + 4846 holdout |
| No test-order information in the optimiser / search / CSP objective (final NN + Swaps) | integration | PASS | Objective, SA and Search use only predicted demand + training pair constraints. The LEGACY optimiser does tune on 1000 dev invoices (kept separately). |
| Training/test leakage inside forecasts.csv & copurchase_pairs.csv | integration | NOT VERIFIABLE | Training window of these Person-1 files was not supplied, so this cannot be verified here. |
| CSP algorithms compared on identical problems | integration | PASS | same pair-constraint set per (protocol, size) for BT / BT+FC / BT+FC+AC-3 |
| CSV exports exist with expected columns | integration | PASS | 9 files checked |
| Figures exist (PNG) with their underlying data CSV | integration | PASS | 11 figures checked |
| Figure data equals the experiment result tables (no invented values) | integration | PASS | four-layout, search and CSP figure data compared with exported results |
| Automated unit tests (tests/ folder, 39 tests) | unit | PASS | 39 passed, 0 failed [] |

## Figures
`figures/`: warehouse_layout, copurchase_network, demand_distribution, csp_execution_time, csp_search_nodes, csp_backtracks, search_objective, search_nodes, search_execution_time, four_layout_distance, four_layout_violations (each with `figures/data/<name>_data.csv`).
