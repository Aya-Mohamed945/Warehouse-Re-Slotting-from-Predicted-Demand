# Assumptions and limitations

## Simulated assumptions (not from the UCI data)
Warehouse geometry, shelf levels, aisles, capacity 100, product category / heavy flag / required capacity (seed 42), and the category-compatibility table. Co-purchase `strength` and `max_distance` come from Person 1's pair file.

## Limitations that cannot honestly be resolved
1. **Strict 120-product problem is infeasible** (31 cleaning products need whole aisles free of food/fragile, 61 food+fragile products need the remaining aisles; no split of 4 aisles ([30, 30, 30, 30] slots) holds both (best slack A/B = (-1, 29))). No full layout can satisfy the aisle rule; each layout reports its incompatible-aisle pairs. Making it feasible needs a changed *assumption* (e.g. 6 aisles x 20 slots or different category mix); this was deliberately not done silently. Effect: the strict experiment at 120 products is a certificate, not a search result.
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
