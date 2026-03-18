"""
Figure 1: NW Alaska map — village medevac activations to Maniilaq Health Center (Kotzebue).
Style aligned with manuscript notebook: borough basemap, flow lines to hub, markers sized by pop and colored by rate.

Layout conventions: docs/map_layout.md
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
MAP_DIR = ROOT / "mapping data"
FAC_SHP = (
    MAP_DIR
    / "Healthcare_Facilities _Healthcare_SafetyNet_Directory"
    / "Healthcare_Facilities%3A_Healthcare_SafetyNet_Directory.shp"
)
BOROUGH_SHP = MAP_DIR / "Boroughs2020" / "Boroughs2020.shp"
# 2020 Census DHC: under-18 count per place (refresh: scripts/fetch_maniilaq_census_pediatric.py)
POP_CSV = ROOT / "docs" / "maniilaq_village_census2020_pediatric.csv"

# Label center in EPSG:3338 m: from village, move (along) away from Kotzebue along hub→village ray,
# then (perp) along perpendicular (m) to separate neighbors. No leader lines — box sits near its village.
_VILLAGE_LABEL_ALONG_PERP_M: dict[str, tuple[float, float]] = {
    "Point Hope": (45_000, -12_000),
    "Kivalina": (26_000, -38_000),
    "Selawik": (44_000, 32_000),
    "Noorvik": (18_000, -28_000),
    "Kiana": (38_000, 24_000),
    "Ambler": (24_000, -18_000),
    "Kobuk": (20_000, 16_000),
    "Shungnak": (18_000, -14_000),
    "Noatak": (48_000, 8000),
    "Deering": (40_000, -26_000),
    "Buckland": (30_000, 26_000),
}

# Borough label nudge in EPSG:3338 m (east, north) after viewport clip
_BOROUGH_LABEL_OFFSET_M: dict[str, tuple[float, float]] = {
    "North Slope Borough": (0.0, 14_000.0),
}

# Annualized label %: (total MHC legs / study years) / pediatric pop × 100
_MHC_LEGS_STUDY_YEARS = 5  # 2020–2024


def _geom_xy(g: object) -> tuple[float, float]:
    if isinstance(g, Point):
        return float(g.x), float(g.y)
    return float(g.centroid.x), float(g.centroid.y)


def _map_bounds_manuscript(gdf_facilities_3338) -> tuple[float, float, float, float]:
    """
    Identical framing to manuscript notebook: Point Hope minx − 50 km,
    Kobuk x + 60 km, Buckland y − 10 km, max village y (excl. Kotzebue) + 20 km (EPSG:3338 m).
    """
    gdf = gdf_facilities_3338
    ph = gdf[gdf["NAME"].str.contains("Point Hope", case=False, na=False)]
    kob = gdf[gdf["NAME"].str.match(r"(?i)kobuk\s*$", na=False)]
    if kob.empty:
        kob = gdf[gdf["NAME"].str.contains("Kobuk", case=False, na=False)]
    buc = gdf[gdf["NAME"].str.contains("Buckland", case=False, na=False)]

    if ph.empty or kob.empty or buc.empty:
        tb = gdf.total_bounds
        pad = 80_000.0
        return tb[0] - pad, tb[2] + pad, tb[1] - pad, tb[3] + pad

    ph_bounds = ph.total_bounds
    adjusted_xmin = float(ph_bounds[0]) - 50_000.0
    kobuk_xmax = _geom_xy(kob.geometry.iloc[0])[0] + 60_000.0
    buckland_ymin = _geom_xy(buc.geometry.iloc[0])[1] - 10_000.0
    non_kot = gdf[gdf["NAME"].str.lower() != "kotzebue"]
    ys = non_kot.geometry.apply(lambda geom: _geom_xy(geom)[1])
    adjusted_ymax = float(ys.max()) + 20_000.0
    return adjusted_xmin, kobuk_xmax, buckland_ymin, adjusted_ymax


def _village_label_center_xy(
    vx: float,
    vy: float,
    hx: float,
    hy: float,
    name: str,
    bx0: float,
    bx1: float,
    by0: float,
    by1: float,
) -> tuple[float, float]:
    along, perp = _VILLAGE_LABEL_ALONG_PERP_M.get(name, (28_000.0, 0.0))
    dx, dy = vx - hx, vy - hy
    d = math.hypot(dx, dy) or 1.0
    ux, uy = dx / d, dy / d
    px, py = -uy, ux
    tx = vx + ux * along + px * perp
    ty = vy + uy * along + py * perp
    mx = (bx1 - bx0) * 0.065
    my = (by1 - by0) * 0.055
    return (
        float(np.clip(tx, bx0 + mx, bx1 - mx)),
        float(np.clip(ty, by0 + my, by1 - my)),
    )


def _borough_label_point_in_view(
    borough_geom,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
):
    """
    Point for borough name text inside the *visible* map extent.
    Full-borough centroids (e.g. North Slope) often sit off-frame; intersect
    with the viewport and label the largest visible polygon.
    """
    from shapely.geometry import box

    view = box(xmin, ymin, xmax, ymax)
    inter = borough_geom.intersection(view)
    if inter.is_empty:
        return borough_geom.representative_point()

    polys: list = []
    if inter.geom_type == "Polygon":
        polys.append(inter)
    elif inter.geom_type == "MultiPolygon":
        polys.extend(inter.geoms)
    elif inter.geom_type == "GeometryCollection":
        for g in inter.geoms:
            if g.geom_type == "Polygon":
                polys.append(g)
            elif g.geom_type == "MultiPolygon":
                polys.extend(g.geoms)

    if not polys:
        return inter.representative_point()
    best = max(polys, key=lambda p: p.area)
    return best.representative_point()


def _village_to_mhc_leg_counts(j: pd.DataFrame, village_names: set[str]) -> Counter[str]:
    """Count medevac legs originating at village clinic with destination CAH (MHC)."""
    c: Counter[str] = Counter()
    j = j.drop_duplicates(subset=["journey_id"])
    for i in range(1, 4):
        fc, tc = f"medevac{i}_from", f"medevac{i}_to"
        for _, r in j.iterrows():
            if pd.isna(r[fc]) or pd.isna(r[tc]):
                continue
            a, b = str(r[fc]).strip(), str(r[tc]).strip()
            if a in village_names and (b == "CAH_01" or b.startswith("CAH_")):
                c[a] += 1
    return c


def plot_fig1_medevac_map(
    journeys: pd.DataFrame,
    village_names: set[str],
    *,
    figsize: tuple[float, float] = (16, 16),
) -> plt.Figure:
    import geopandas as gpd
    from shapely.geometry import LineString, Point

    if not FAC_SHP.is_file() or not BOROUGH_SHP.is_file():
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "Missing shapefiles under mapping data/. Add borough + healthcare facility layers.",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_axis_off()
        return fig

    counts = _village_to_mhc_leg_counts(journeys, village_names)
    fac = gpd.read_file(FAC_SHP)
    man_full = fac[fac["ManagingOr"] == "Maniilaq Association"].copy()
    man_full = man_full.rename(columns={"CommunityN": "NAME"})
    man_full["NAME"] = man_full["NAME"].astype(str).str.strip()
    man_full_g = gpd.GeoDataFrame(man_full, geometry="geometry", crs=fac.crs).to_crs(
        epsg=3338
    )

    names_plot = list(village_names) + ["Kotzebue"]
    man = man_full[
        man_full["NAME"].isin(names_plot) | man_full["NAME"].str.lower().eq("kotzebue")
    ].copy()
    man.loc[man["NAME"].str.lower() == "kotzebue", "NAME"] = "Kotzebue"
    man = man.drop_duplicates(subset=["NAME"])

    pop = pd.read_csv(POP_CSV)
    man = man.merge(pop, on="NAME", how="left")
    man["medevac_count"] = man["NAME"].map(lambda n: int(counts.get(n, 0)))
    man["pediatric_pop_census"] = man["pediatric_pop"]
    med_ped = float(man["pediatric_pop"].median())
    man["pediatric_pop"] = man["pediatric_pop"].fillna(med_ped).clip(lower=1)
    # Rate: MHC-bound legs per 1,000 residents under 18 (2020 Census DHC)
    man["rate_per_1k"] = (man["medevac_count"] / man["pediatric_pop"]) * 1000.0

    # GeoDataFrame in Alaska projected CRS
    man_g = gpd.GeoDataFrame(man, geometry="geometry", crs=fac.crs).to_crs(epsg=3338)

    bor = gpd.read_file(BOROUGH_SHP)
    bor = bor[bor["STATE"] == "02"].to_crs(epsg=3338)
    nw = bor[bor["NAME"].str.contains("Northwest Arctic|North Slope", case=False, na=False)].to_crs(
        epsg=3338
    )

    kot = man_g[man_g["NAME"].str.lower() == "kotzebue"]
    if kot.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "Kotzebue not found in facility layer.", ha="center", va="center")
        ax.set_axis_off()
        return fig
    hub_pt = kot.geometry.iloc[0]
    if not isinstance(hub_pt, Point):
        hub_pt = hub_pt.centroid

    # Line width scales with leg count; keep max modest so routes stay readable
    min_lw, max_lw = 0.5, 2.75
    mc_pos = man_g.loc[man_g["medevac_count"] > 0, "medevac_count"]
    if len(mc_pos) == 0:
        mn, mx = 0, 1
    else:
        mn, mx = int(mc_pos.min()), int(mc_pos.max())
    if mx <= mn:
        mx = mn + 1

    def leg_lw(n: int) -> float:
        if n <= 0:
            return 0.35
        return min_lw + (n - mn) / (mx - mn) * (max_lw - min_lw)

    colorbar_min, colorbar_max = 0, max(80.0, float(man_g["rate_per_1k"].quantile(0.95)) + 5)
    gs_cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "reds_med", plt.get_cmap("Reds")(np.linspace(0.15, 1.0, 256))
    )
    rate_norm = mcolors.Normalize(vmin=colorbar_min, vmax=colorbar_max)

    non_kot = man_g[man_g["NAME"].str.lower() != "kotzebue"].copy()
    pk = non_kot["pediatric_pop"]
    pmin, pmax = float(pk.min()), float(pk.max()) if len(pk) else (1, 1)
    ms_min, ms_max = 120, 1800

    def marker_size(popv: float) -> float:
        if pmax <= pmin:
            return (ms_min + ms_max) / 2
        return ms_min + (popv - pmin) / (pmax - pmin) * (ms_max - ms_min)

    # Map extent (EPSG:3338 m) — same values later applied with set_xlim/set_ylim
    bx0, bx1, by0, by1 = _map_bounds_manuscript(man_full_g)

    fig, ax = plt.subplots(figsize=figsize)
    fs_title, fs_cbar_lbl, fs_cbar_tick = 17, 13, 11
    fs_xlab, fs_leg, fs_borough = 12, 11, 14
    fs_village, fs_hub = 10, 13

    bor.plot(ax=ax, color="lightgrey", edgecolor="black", alpha=0.25, linewidth=0.3)
    nw.plot(ax=ax, color="gainsboro", edgecolor="black", linewidth=0.5)

    for _, brow in nw.iterrows():
        bname = str(brow.get("NAME", ""))
        if "Northwest Arctic" in bname:
            lbl = "Northwest Arctic Borough"
        elif "North Slope" in bname:
            lbl = "North Slope Borough"
        else:
            continue
        g = brow.geometry
        c = _borough_label_point_in_view(g, bx0, bx1, by0, by1)
        mx, my = _BOROUGH_LABEL_OFFSET_M.get(lbl, (0.0, 0.0))
        ax.text(
            float(c.x) + mx,
            float(c.y) + my,
            lbl,
            ha="center",
            va="center",
            fontsize=fs_borough,
            color="0.4",
            alpha=0.55,
            fontstyle="italic",
            zorder=1,
        )

    for _, row in non_kot.iterrows():
        vg = row.geometry
        if not isinstance(vg, Point):
            vg = vg.centroid
        nleg = int(row["medevac_count"])
        col = gs_cmap(rate_norm(np.clip(row["rate_per_1k"], colorbar_min, colorbar_max)))
        lw = leg_lw(nleg)
        alpha = 0.88 if nleg > 0 else 0.25
        line_col = col if nleg > 0 else (0.75, 0.75, 0.75, 0.6)
        line = LineString([vg, hub_pt])
        ax.plot(*line.xy, color=line_col, linewidth=lw, alpha=alpha, zorder=4, solid_capstyle="round")

    for _, row in non_kot.iterrows():
        vg = row.geometry
        if not isinstance(vg, Point):
            vg = vg.centroid
        nleg = int(row["medevac_count"])
        dot_col = gs_cmap(rate_norm(np.clip(row["rate_per_1k"], colorbar_min, colorbar_max)))
        if nleg < 1:
            dot_col = (0.85, 0.85, 0.85)
        ax.scatter(
            vg.x,
            vg.y,
            s=marker_size(float(row["pediatric_pop"])),
            c=[dot_col],
            edgecolors="white",
            linewidths=0.8,
            zorder=5,
        )

    ax.scatter(
        hub_pt.x,
        hub_pt.y,
        s=2400,
        c="black",
        edgecolors="white",
        linewidths=1.5,
        zorder=6,
        marker="s",
    )

    def _village_verbose_label(r: pd.Series) -> str:
        name = str(r["NAME"])
        ped = r.get("pediatric_pop_census")
        ped_i = int(ped) if pd.notna(ped) else int(r["pediatric_pop"])
        nleg = int(r["medevac_count"])
        if ped_i > 0:
            pct_yr = 100.0 * (nleg / _MHC_LEGS_STUDY_YEARS) / ped_i
        else:
            pct_yr = float("nan")
        pct_s = f"{pct_yr:.1f}" if pd.notna(pct_yr) else "—"
        return (
            f"{name} (pediatric pop {ped_i})\n"
            f"n= {nleg} medevacs\n"
            f"{pct_s}% of children w/ medevac per year"
        )

    for _, row in non_kot.iterrows():
        name = str(row["NAME"])
        vg = row.geometry
        if not isinstance(vg, Point):
            vg = vg.centroid
        tcx, tcy = _village_label_center_xy(
            float(vg.x),
            float(vg.y),
            float(hub_pt.x),
            float(hub_pt.y),
            name,
            bx0,
            bx1,
            by0,
            by1,
        )
        ax.annotate(
            _village_verbose_label(row),
            xy=(float(vg.x), float(vg.y)),
            xytext=(tcx, tcy),
            textcoords="data",
            ha="center",
            va="center",
            fontsize=fs_village,
            linespacing=1.1,
            bbox=dict(
                boxstyle="round,pad=0.26",
                facecolor="white",
                edgecolor="0.55",
                alpha=0.93,
                linewidth=0.45,
            ),
            zorder=7,
        )

    sm = plt.cm.ScalarMappable(cmap=gs_cmap, norm=rate_norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.45, pad=0.02)
    cbar.set_label(
        "Medevac legs to MHC per 1,000 residents under 18 (2020 Census)",
        fontsize=fs_cbar_lbl,
    )
    cbar.ax.tick_params(labelsize=fs_cbar_tick)

    ax.set_title(
        "Figure 1. Pediatric medevac activations to Maniilaq Health Center by village clinic",
        fontsize=fs_title,
        pad=14,
    )
    ax.set_xlabel("Alaska Albers (m)", fontsize=fs_xlab)
    ax.set_ylabel("")
    ax.axis("off")

    from matplotlib.lines import Line2D

    leg = ax.legend(
        handles=[
            Line2D([0], [0], color="0.4", lw=2.2, label="Thicker line = more MHC-bound legs"),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="0.5",
                markersize=11,
                label="Larger dot = more residents <18 (2020 Census)",
            ),
            Line2D(
                [0],
                [0],
                marker="s",
                color="w",
                markerfacecolor="black",
                markeredgecolor="white",
                markeredgewidth=0.8,
                markersize=10,
                linestyle="None",
                label="MHC (Kotzebue)",
            ),
        ],
        loc="lower left",
        fontsize=fs_leg,
        framealpha=0.95,
    )

    ax.set_xlim(bx0, bx1)
    ax.set_ylim(by0, by1)
    ax.set_aspect("equal")
    fig.tight_layout()

    ax.annotate(
        "Maniilaq Health Center\n(Kotzebue)",
        xy=(float(hub_pt.x), float(hub_pt.y)),
        xytext=(float(hub_pt.x), float(hub_pt.y)),
        textcoords="data",
        ha="center",
        va="center",
        fontsize=fs_hub,
        fontweight="bold",
        color="black",
        bbox=dict(
            boxstyle="round,pad=0.22",
            facecolor="white",
            edgecolor="0.35",
            alpha=0.96,
            linewidth=0.6,
        ),
        zorder=12,
    )

    return fig
