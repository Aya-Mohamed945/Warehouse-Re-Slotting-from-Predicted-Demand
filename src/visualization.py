"""Presentation-ready dark-theme figures (300 DPI PNG) + the data behind each figure."""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
from matplotlib.lines import Line2D
from .warehouse import ROWS, COLS, DEPOT, manhattan

BG, FG, GRID = "#0f1419", "#f2f4f8", "#3a4350"
CAT_COLORS = {"food": "#F4A261", "cleaning": "#2EC4B6", "stationery": "#8D99FF", "fragile": "#FF5C8A"}
ALG_COLORS = {"BT": "#FF6B6B", "BT+FC": "#4DD0E1", "BT+FC+AC-3": "#FFD166"}
SEARCH_COLORS = {"Greedy Best-First": "#F72585", "Bounded UCS": "#4CC9F0", "A* variant": "#FFD60A"}
LAYOUT_COLORS = {"Random": "#9AA5B1", "Last-week demand": "#FFB703", "NN demand": "#4CC9F0",
                 "NN + Swaps": "#80ED99"}
DPI = 300


def _style():
    plt.rcParams.update({
        "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
        "text.color": FG, "axes.labelcolor": FG, "axes.edgecolor": GRID,
        "xtick.color": FG, "ytick.color": FG, "axes.titlecolor": FG,
        "grid.color": GRID, "font.size": 10, "legend.facecolor": "#1a212b",
        "legend.edgecolor": GRID, "legend.labelcolor": FG,
    })


def _finish(fig, path, caption, data=None, data_dir=None):
    fig.text(0.5, -0.02, caption, ha="center", va="top", fontsize=8.5, color="#c5ccd6",
             wrap=True, style="italic")
    fig.savefig(path, dpi=DPI, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    if data is not None and data_dir:
        os.makedirs(data_dir, exist_ok=True)
        data.to_csv(os.path.join(data_dir, os.path.splitext(os.path.basename(path))[0] + "_data.csv"),
                    index=False)


def _bars(ax, groups, series, colors, ylabel, log=False, fmt="{:g}", hatch_map=None, title=None):
    x = np.arange(len(groups))
    k = len(series)
    w = 0.8 / k
    for i, (name, vals) in enumerate(series.items()):
        pos = x - 0.4 + w * (i + 0.5)
        bars = ax.bar(pos, vals, w * 0.92, color=colors[name], label=name, edgecolor=BG,
                      hatch=(hatch_map or {}).get((name,), None))
        for b, v, xx in zip(bars, vals, pos):
            if v != v:
                continue
            ax.text(xx, max(b.get_height(), 0), fmt.format(v), ha="center", va="bottom",
                    fontsize=7.5, color=FG, rotation=0 if k < 4 else 90)
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.set_ylabel(ylabel)
    if log == "log":
        ax.set_yscale("log")
    elif log:
        ax.set_yscale("symlog", linthresh=1)
    ax.grid(axis="y", alpha=0.35)
    ax.set_axisbelow(True)
    if title:
        ax.set_title(title, fontsize=10.5)


# ======================================================================= warehouse map
def fig_warehouse_layout(products, layout, slots, pairs, path, data_dir, title_suffix="NN + Swaps layout"):
    _style()
    pby = {p["id"]: p for p in products}
    where = {pid: next(s for s in slots if s.slot_id == sid) for pid, sid in layout.items()}
    dmax = max(p["demand"] for p in products)
    fig, ax = plt.subplots(figsize=(17, 10.8))
    rows = []
    for pid, s in where.items():
        p = pby[pid]
        intensity = 0.25 + 0.75 * (np.log1p(p["demand"]) / np.log1p(dmax))
        ax.add_patch(Rectangle((s.col, s.row), 1, 1, facecolor=CAT_COLORS[p["category"]],
                               alpha=float(intensity), edgecolor=BG, lw=1.2,
                               hatch="////" if p["heavy"] else None))
        ax.text(s.col + 0.5, s.row + 0.42, pid, ha="center", va="center", fontsize=7.4,
                color="white", weight="bold")
        ax.text(s.col + 0.5, s.row + 0.74, f"{p['demand']:.0f}", ha="center", va="center",
                fontsize=6.2, color="#e8ecf2")
        rows.append({"product_id": pid, "row": s.row, "col": s.col, "aisle": s.aisle + 1, "level": s.level,
                     "category": p["category"], "heavy": p["heavy"], "predicted_demand": p["demand"]})
    for a in range(1, 4):                                    # aisle boundaries = walking corridors
        ax.axvline(a * 3, color="#ffffff", lw=2.2, ls=(0, (4, 3)))
    for a in range(4):
        ax.text(a * 3 + 1.5, -0.55, f"Aisle {a + 1}", ha="center", color=FG, fontsize=11, weight="bold")
    for lvl, r0, r1 in (("LOW shelf (rows 0-3)", 0, 4), ("MIDDLE shelf (rows 4-6)", 4, 7),
                        ("HIGH shelf (rows 7-9)", 7, 10)):
        ax.text(-1.05, (r0 + r1) / 2, lvl, rotation=90, ha="right", va="center", fontsize=9, color="#c5ccd6")
        if r0:
            ax.axhline(r0, color="#c5ccd6", lw=1.0, ls=":")
    ax.add_patch(Rectangle((0, 0), 1, 1, fill=False, edgecolor="#ffe66d", lw=3.5))
    ax.annotate("DEPOT (0,0)", (0.5, 0.0), (1.6, -1.25), color="#ffe66d", fontsize=10, weight="bold",
                arrowprops=dict(arrowstyle="->", color="#ffe66d"))
    top = pairs[:15]
    for a, b, d, st in top:
        sa, sb = where[a], where[b]
        dist = manhattan(sa.pos, sb.pos)
        ok = dist <= d
        ax.plot([sa.col + .5, sb.col + .5], [sa.row + .5, sb.row + .5],
                color="#7CFC00" if ok else "#FF3B3B", lw=0.8 + 4.0 * st / 950, alpha=0.9, zorder=5)
    ax.set_xlim(-1.3, COLS)
    ax.set_ylim(ROWS, -1.9)
    ax.set_aspect("equal")
    ax.set_xticks(np.arange(COLS) + .5, labels=[f"c{c}" for c in range(COLS)])
    ax.set_yticks(np.arange(ROWS) + .5, labels=[f"r{r}" for r in range(ROWS)])
    ax.tick_params(length=0, labelsize=8)
    ax.set_xlabel("Column (grid units; Manhattan distance = |Δrow| + |Δcol|)")
    ax.set_ylabel("Row (distance from Depot side)")
    ax.set_title(f"Warehouse map - 10×12 grid, 120 slots, {title_suffix}", fontsize=14, pad=14)
    handles = [Patch(facecolor=c, label=k.capitalize()) for k, c in CAT_COLORS.items()]
    handles += [Patch(facecolor="#555", hatch="////", edgecolor=FG, label="Heavy product (low shelf only)"),
                Line2D([0], [0], color="#7CFC00", lw=3, label="Top-15 co-purchase pair: within limit"),
                Line2D([0], [0], color="#FF3B3B", lw=3, label="Top-15 co-purchase pair: too far (violated)"),
                Line2D([0], [0], color="white", lw=2, ls="--", label="Aisle boundary / walking corridor"),
                Patch(facecolor="none", edgecolor="#ffe66d", lw=2, label="Depot")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.085), ncol=5, fontsize=9)
    fig.text(0.5, 0.995, "Cell text: product id (top) and predicted weekly demand (bottom). Colour brightness ∝ log demand; "
             "line width ∝ co-purchase strength.", ha="center", va="top", fontsize=9, color="#c5ccd6")
    _finish(fig, path, "Caption: the generated warehouse (shelf levels, aisles and categories are simulated assumptions). "
            "High-demand items sit near the Depot; red lines show co-purchase pairs the soft optimiser could not bring within their limit.",
            pd.DataFrame(rows), data_dir)


# ======================================================================= co-purchase network
def fig_copurchase_network(products, pairs, layout, slots, path, data_dir, top=25):
    import networkx as nx
    _style()
    pby = {p["id"]: p for p in products}
    sl = {s.slot_id: s for s in slots}
    use = pairs[:top]
    G = nx.Graph()
    for a, b, d, st in use:
        G.add_edge(a, b, strength=st, dmax=d)
    pos = nx.spring_layout(G, seed=7, k=0.9, weight="strength")
    fig, ax = plt.subplots(figsize=(14, 9.5))
    data = []
    for a, b, d, st in use:
        dist = manhattan(sl[layout[a]].pos, sl[layout[b]].pos)
        ax.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]], color="#dfe6ee",
                lw=0.6 + 7.0 * (st - 330) / (950 - 330), alpha=0.55, zorder=1)
        data.append({"product_a": a, "product_b": b, "strength": st, "max_distance": d,
                     "distance_in_final_layout": dist, "violated": dist > d})
    for n in G.nodes:
        p = pby[n]
        ax.scatter(*pos[n], s=250 + 1500 * p["demand"] / max(q["demand"] for q in products),
                   color=CAT_COLORS[p["category"]], edgecolor="white", lw=1.2, zorder=3)
        ax.text(pos[n][0], pos[n][1] - 0.075, n, ha="center", va="top", fontsize=8, color=FG, zorder=4)
    ax.axis("off")
    ax.set_title(f"Strongest {top} co-purchase relationships (training-derived)", fontsize=14)
    ax.legend(handles=[Patch(facecolor=c, label=k.capitalize()) for k, c in CAT_COLORS.items()] +
              [Line2D([0], [0], color="#dfe6ee", lw=5, label="Line width ∝ pair strength (co-purchase count)")],
              loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=5)
    _finish(fig, path, "Caption: products frequently bought on the same invoice should be shelved within a few grid cells "
            "(limit 2-6) so one picker trip collects both. Node size ∝ predicted demand. All 200 pairs are in copurchase_pairs_all.csv.",
            pd.DataFrame(data), data_dir)


# ======================================================================= demand
def fig_demand_distribution(products, layouts, slots, path, data_dir):
    _style()
    sl = {s.slot_id: s for s in slots}
    pby = {p["id"]: p for p in products}
    fig, axes = plt.subplots(1, 4, figsize=(26, 6.5), gridspec_kw={"width_ratios": [1.3, 1, 1.1, 0.9]})
    ax = axes[0]
    top = products[:30]
    ax.bar(range(30), [p["demand"] for p in top], color=[CAT_COLORS[p["category"]] for p in top])
    ax.set_xticks(range(30), [p["id"] for p in top], rotation=90, fontsize=7)
    ax.set_ylabel("Predicted next-week demand (units)")
    ax.set_title("Predicted demand, 30 highest-demand products")
    ax.legend(handles=[Patch(facecolor=c, label=k.capitalize()) for k, c in CAT_COLORS.items()], fontsize=8)
    ax.grid(axis="y", alpha=.3)
    ax = axes[1]
    rows = []
    for name, col, mk in (("NN demand", LAYOUT_COLORS["NN demand"], "o"), ("NN + Swaps", LAYOUT_COLORS["NN + Swaps"], "^")):
        lay = layouts[name]
        xs = [manhattan(sl[lay[p["id"]]].pos, DEPOT) for p in products]
        ax.scatter(xs, [p["demand"] for p in products], s=28, color=col, alpha=.75, marker=mk, label=name)
        rows += [{"layout": name, "product_id": p["id"], "demand": p["demand"], "distance_to_depot": x}
                 for p, x in zip(products, xs)]
    ax.set_yscale("log")
    ax.set_xlabel("Manhattan distance of the product's slot from the Depot (grid units)")
    ax.set_ylabel("Predicted demand (units, log scale)")
    ax.set_title("Demand vs. placement distance")
    ax.legend(fontsize=8)
    ax.grid(alpha=.3)
    ax = axes[2]
    agg = {}
    for name, lay in layouts.items():
        a = [0.0] * 4
        for pid, sid in lay.items():
            a[sl[sid].aisle] += pby[pid]["demand"]
        agg[name] = a
        rows += [{"layout": name, "aisle": i + 1, "aisle_demand": v, "kind": "aisle_total"} for i, v in enumerate(a)]
    _bars(ax, [f"Aisle {i + 1}" for i in range(4)], agg, LAYOUT_COLORS, "Total predicted demand in aisle (units)",
          fmt="{:.0f}", title="Demand distribution by aisle")
    ax.legend(fontsize=8)
    for a_ in axes[2].texts:
        a_.set_fontsize(6.5)
    ax = axes[3]
    lay = layouts["NN + Swaps"]
    bottom = np.zeros(4)
    for cat, colr in CAT_COLORS.items():
        cnt = np.zeros(4)
        for pid, sid in lay.items():
            if pby[pid]["category"] == cat:
                cnt[sl[sid].aisle] += 1
        ax.bar([f"Aisle {i + 1}" for i in range(4)], cnt, bottom=bottom, color=colr, label=cat.capitalize(), edgecolor=BG)
        rows += [{"layout": "NN + Swaps", "aisle": i + 1, "category": cat, "product_count": int(cnt[i]), "kind": "aisle_category_count"} for i in range(4)]
        bottom += cnt
    ax.set_ylabel("Products in aisle (count; 30 slots per aisle)")
    ax.set_ylim(0, 38)
    ax.set_title("Product counts per aisle (NN + Swaps)")
    ax.legend(fontsize=8)
    _finish(fig, path, "Caption: left - demand is highly skewed; middle - the optimised layout keeps high-demand items near the Depot; "
            "third - predicted demand carried by each aisle; right - product counts per aisle and category in the final layout.", pd.DataFrame(rows), data_dir)


# ======================================================================= CSP figures
def _csp_panel_fig(df, value, ylabel, title, path, data_dir, caption, log=True):
    caption = caption.replace("⏱", "LIMIT")
    _style()
    protos = list(dict.fromkeys(df["Protocol"]))
    fig, axes = plt.subplots(1, len(protos), figsize=(6.6 * len(protos), 6.2), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, proto in zip(axes, protos):
        d = df[df["Protocol"] == proto]
        sizes = sorted(d["Products"].unique())
        series = {a: [float("nan") if d[(d.Products == n) & (d.Algorithm == a)]["Status"].iloc[0].startswith("INFEASIBLE") else float(d[(d.Products == n) & (d.Algorithm == a)][value].iloc[0]) for n in sizes] for a in ALG_COLORS}
        _bars(ax, [f"{n} products" for n in sizes], series, ALG_COLORS, ylabel, log=log, fmt="{:,.4g}",
              title=proto if proto.startswith("Diag") else f"Strict protocol {proto}")
        ax.set_xlim(-0.6, len(sizes) - 0.4)
        for i, n in enumerate(sizes):
            if all(d[(d.Products == n) & (d.Algorithm == a)]["Status"].iloc[0].startswith("INFEASIBLE") for a in ALG_COLORS):
                ax.text(i, 0.5, "INFEASIBLE\n(exact certificate:\nno search run)", ha="center", va="center", fontsize=9.5,
                        color="#ffffff", weight="bold", transform=ax.get_xaxis_transform(),
                        bbox=dict(boxstyle="round", facecolor="#5a1f2b", edgecolor="#FF5C8A"))
                continue
            for j, a in enumerate(ALG_COLORS):
                r = d[(d.Products == n) & (d.Algorithm == a)].iloc[0]
                if r["Status"] != "SOLVED":
                    xx = i - 0.4 + (0.8 / 3) * (j + 0.5)
                    ax.text(xx, 0.03, "LIMIT" if "TIME" in r["Status"] else "NODE LIMIT", ha="center", va="bottom", rotation=90,
                            fontsize=8, color="#0f1419", weight="bold", transform=ax.get_xaxis_transform())
    axes[0].legend(title="Algorithm", fontsize=9)
    fig.suptitle(title, fontsize=14)
    _finish(fig, path, caption, df[["Products", "Algorithm", "Protocol", "Status", value]], data_dir)


def fig_csp_time(df, path, data_dir):
    _csp_panel_fig(df, "Time (s)", "Execution time (seconds, log scale)", "CSP execution time by algorithm and problem size",
                   path, data_dir, "Caption: INFEASIBLE = exact counting certificate shows the strict aisle rule cannot be met, so no search was run; LIMIT = stopped at the time limit (20 s; 45 s in the diagnostic; not a proof). "
                   "Right panel is a diagnostic with only the aisle rule relaxed.", log="log")


def fig_csp_nodes(df, path, data_dir):
    _csp_panel_fig(df, "Nodes", "Search nodes (symlog scale)", "CSP search nodes by algorithm and problem size",
                   path, data_dir, "Caption: nodes = recursive calls. LIMIT marks runs stopped by the time limit (lower bounds on the work needed); INFEASIBLE = exact certificate, no search run.")


def fig_csp_backtracks(df, path, data_dir):
    _csp_panel_fig(df, "Backtracks", "Backtracks (symlog scale)", "CSP backtracks by algorithm and problem size",
                   path, data_dir, "Caption: backtrack = an assignment undone without leading to a solution. LIMIT marks runs stopped by the time limit; INFEASIBLE = exact certificate, no search run.")


# ======================================================================= search figures
def _search_bar(df, col, ylabel, title, path, data_dir, caption, fmt="{:,.4g}", log=False):
    _style()
    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    series = {a: [float(df[df.Algorithm == a][col].iloc[0])] for a in SEARCH_COLORS}
    _bars(ax, [""], series, SEARCH_COLORS, ylabel, log=log, fmt=fmt)
    ax.set_title(title)
    ax.legend()
    ax.set_xticks([])
    _finish(fig, path, caption, df[["Algorithm", col]], data_dir)


def fig_search_all(df, fig_dir, data_dir):
    p = lambda n: os.path.join(fig_dir, n)
    init = df["initial_objective"].iloc[0]
    tgt = df["target_objective"].iloc[0]
    _style()
    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    series = {a: [float(df[df.Algorithm == a]["final_objective"].iloc[0])] for a in SEARCH_COLORS}
    _bars(ax, [""], series, SEARCH_COLORS, "Final objective J (lower is better)", fmt="{:.3f}")
    ax.axhline(init, color="#ffffff", ls="--", lw=1.3)
    ax.text(0.45, init, f" initial J = {init:.3f}", color="#ffffff", va="bottom", ha="right", fontsize=9)
    ax.axhline(tgt, color="#7CFC00", ls=":", lw=1.5)
    ax.text(0.45, tgt, f" target J = {tgt:.3f}", color="#7CFC00", va="top", ha="right", fontsize=9)
    ax.set_ylim(min(tgt, df["final_objective"].min()) * 0.95, init * 1.03)
    ax.set_xticks([])
    ax.set_title("Search: final objective by algorithm")
    ax.legend(loc="lower left")
    _finish(fig, p("search_objective.png"), "Caption: J = demand-weighted walking distance + 0.04 × total pair excess. "
            "Dashed = starting layout, dotted = goal (90 % of initial J). Axis is truncated to show the differences.",
            df[["Algorithm", "initial_objective", "final_objective", "target_objective"]], data_dir)
    _search_bar(df, "expanded_nodes", "Expanded nodes", "Search: expanded nodes", p("search_nodes.png"), data_dir,
                "Caption: nodes popped from the frontier and expanded (budget: 300 expansions, depth ≤ 6).", fmt="{:,.0f}")
    _search_bar(df, "seconds", "Execution time (seconds)", "Search: execution time", p("search_execution_time.png"), data_dir,
                "Caption: wall-clock time of one deterministic run per algorithm.", fmt="{:.2f}")


# ======================================================================= four-layout figures
def fig_four_layouts(df, fig_dir, data_dir):
    _style()
    names = list(LAYOUT_COLORS)
    d = df.set_index("Layout").loc[names].reset_index()
    cols = [LAYOUT_COLORS[n] for n in names]

    def panel(ax, col, ylabel, title, fmt, ylim=None):
        b = ax.bar(names, d[col], color=cols, edgecolor=BG)
        for r, v in zip(b, d[col]):
            ax.text(r.get_x() + r.get_width() / 2, r.get_height(), fmt.format(v), ha="center", va="bottom", fontsize=9)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.tick_params(axis="x", labelrotation=12)
        ax.grid(axis="y", alpha=.35)
        ax.set_axisbelow(True)
        if ylim:
            ax.set_ylim(*ylim)
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    panel(axes[0], "Average distance per invoice", "Average picker distance per invoice (grid units)", "Average picker distance", "{:.3f}",
          (0, d["Average distance per invoice"].max() * 1.12))
    panel(axes[1], "Total picker distance", "Total picker distance over held-out invoices (grid units)", "Total picker distance", "{:,.0f}",
          (0, d["Total picker distance"].max() * 1.12))
    fig.suptitle("Four-layout comparison on held-out invoices - picker distance", fontsize=14)
    _finish(fig, os.path.join(fig_dir, "four_layout_distance.png"),
            "Caption: same invoices, same warehouse, same nearest-neighbour route model for every layout (route is a heuristic, not an optimal TSP tour).",
            d[["Layout", "Invoices evaluated", "Average distance per invoice", "Total picker distance"]], data_dir)
    fig, axes = plt.subplots(1, 3, figsize=(21, 6))
    panel(axes[2], "Incompatible aisle pairs", "Incompatible-category product pairs sharing an aisle", "Category-aisle violations", "{:.0f}",
          (0, d["Incompatible aisle pairs"].max() * 1.15))
    panel(axes[0], "Pair violations", "Co-purchase pairs farther apart than allowed (of 200)", "Pair violations", "{:.0f}",
          (0, d["Pair violations"].max() * 1.15))
    panel(axes[1], "Total excess distance", "Σ (distance - max allowed) over violated pairs (grid units)", "Total excess distance", "{:.0f}",
          (0, d["Total excess distance"].max() * 1.15))
    fig.suptitle("Four-layout comparison - co-purchase constraint violations", fontsize=14)
    _finish(fig, os.path.join(fig_dir, "four_layout_violations.png"),
            "Caption: violations are a property of the layout (independent of invoices). Lower is better. The aisle rule cannot reach 0 for 120 products (infeasible), so a small residual is expected.",
            d[["Layout", "Pair violations", "Total excess distance", "Incompatible aisle pairs"]], data_dir)
