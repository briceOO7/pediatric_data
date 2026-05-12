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
MAP_DIR = ROOT / "mapping_data"
FAC_SHP = MAP_DIR / "healthcare_facilities_safetynet" / "healthcare_facilities_safetynet.shp"
BOROUGH_SHP = MAP_DIR / "Boroughs2020" / "Boroughs2020.shp"
PLACES_SHP = MAP_DIR / "alaska2019" / "tl_2019_02_place.shp"
# 2020 Census DHC: under-18 count per place (refresh: scripts/fetch_maniilaq_census_pediatric.py)
POP_CSV = ROOT / "docs" / "maniilaq_village_census2020_pediatric.csv"
VILLAGE_CODEBOOK_CSV = ROOT / "docs" / "village_name_codebook.csv"

# ── Label placement groups (EPSG:3338 m) ────────────────────────────────────
# Fixed-right  : label left-edge starts to the right of the dot, vertically centered
_LABEL_FIXED_RIGHT: frozenset[str] = frozenset({"Point Hope", "Kivalina", "Noatak", "Buckland"})
# Fixed-above  : label centered above the dot
_LABEL_FIXED_ABOVE: frozenset[str] = frozenset({"Deering", "Kiana", "Ambler"})
# Fixed-below  : label centered below the dot
_LABEL_FIXED_BELOW: frozenset[str] = frozenset({"Selawik", "Shungnak"})
# Fixed-below, right-aligned to dot centre (right margin = dot x)
_LABEL_FIXED_BELOW_RIGHT: frozenset[str] = frozenset({"Noorvik"})
# Radial placement with a thin leader line drawn to the dot
# (Kobuk placed above-left of Ambler label area, line drawn back to Kobuk dot)

_LABEL_OFFSET_RIGHT_M: float = 8_000.0    # gap from dot centre to text left edge
_LABEL_OFFSET_VERT_M: float  = 4_000.0    # gap from dot centre to text top/bottom

# Radial placement for leader-line villages: not used for Kobuk (special override below)
_VILLAGE_LABEL_ALONG_PERP_M: dict[str, tuple[float, float]] = {}

# Villages whose label is placed at a fixed absolute offset (dx, dy in m) from their dot,
# with a leader line drawn. Format: name -> (dx_m, dy_m, ha, va)
_VILLAGE_LABEL_ABSOLUTE_OFFSET_M: dict[str, tuple[float, float, str, str]] = {
    "Kobuk": (0.0, 50_000.0, "center", "bottom"),
}

# Borough label nudge in EPSG:3338 m (east, north) after viewport clip
_BOROUGH_LABEL_OFFSET_M: dict[str, tuple[float, float]] = {
    "Northwest Arctic Borough": (0.0, 14_000.0),  # (east, north) m — nudge label north
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


def _census_village_names_excl_hub() -> frozenset[str]:
    """Community names with pediatric census rows (excl. Kotzebue = hub)."""
    pop = pd.read_csv(POP_CSV)
    return frozenset(pop["NAME"].astype(str).str.strip()) - {"Kotzebue"}


def _is_hub_facility_medevac_origin(s: str) -> bool:
    """Same facility-code rule as medevac_summaries._is_study_facility_origin."""
    t = str(s).strip()
    if not t:
        return True
    u = t.upper().replace("_", "")
    if u.startswith("CAH") or u.startswith("HUB") or "OUTSIDEHOSPITAL" in u:
        return True
    return False


def _is_mhc_destination_label(s: str) -> bool:
    """Accept CAH/MHC variants for Maniilaq destination labels in PHI exports."""
    b = str(s).strip()
    bl = b.lower()
    return (
        b == "CAH_01"
        or b.startswith("CAH")
        or b.upper() == "MHC"
        or " mhc" in f" {bl}"
        or "maniilaq health center" in bl
        or (("maniilaq" in bl) and ("health" in bl) and ("center" in bl))
    )


def _canonical_census_village(origin: str, census: frozenset[str]) -> str | None:
    a = str(origin).strip()
    if a in census:
        return a
    # Local synthetic fallback: Village_* placeholders -> community names.
    if a.startswith("Village_") and VILLAGE_CODEBOOK_CSV.is_file():
        try:
            cb = pd.read_csv(VILLAGE_CODEBOOK_CSV)
            m = dict(
                zip(
                    cb["anonymous_code"].astype(str),
                    cb["community_name"].astype(str),
                    strict=True,
                )
            )
            b = m.get(a)
            if b in census:
                return b
        except Exception:
            pass
    by_lower = {n.lower(): n for n in census}
    return by_lower.get(a.lower())


def _village_to_mhc_leg_counts(
    j: pd.DataFrame,
    village_names: set[str],
    *,
    infer: bool = False,
) -> Counter[str]:
    """Count medevac legs originating at village clinic with destination CAH (MHC)."""
    c: Counter[str] = Counter()
    j = j.drop_duplicates(subset=["journey_id"])
    census = _census_village_names_excl_hub() if infer else None
    for i in range(1, 4):
        fc, tc = f"medevac{i}_from", f"medevac{i}_to"
        for _, r in j.iterrows():
            if pd.isna(r[fc]) or pd.isna(r[tc]):
                continue
            a, b = str(r[fc]).strip(), str(r[tc]).strip()
            # PHI fallback: first leg origin may be encoded as non-village medevac origin
            # while facility_1_name still records the village clinic start.
            if i == 1 and (not a or _is_hub_facility_medevac_origin(a)):
                f1 = str(r.get("facility_1_name", "")).strip()
                if f1:
                    a = f1
            if not _is_mhc_destination_label(b):
                continue
            if infer:
                if _is_hub_facility_medevac_origin(a) or census is None:
                    continue
                key = _canonical_census_village(a, census)
                if key is None:
                    continue
                a = key
            elif a not in village_names:
                continue
            c[a] += 1
    return c


def _voronoi_polygons_clipped(points_xy: np.ndarray, clip_geom):
    """
    Compute finite Voronoi polygons for *points_xy* clipped to *clip_geom*.

    Returns a list of shapely Polygon/MultiPolygon objects in the same order
    as *points_xy*.  Uses far-field dummy points so no region is unbounded.
    """
    from scipy.spatial import Voronoi
    from shapely.geometry import MultiPoint
    from shapely.ops import unary_union

    # Pad with dummy points well outside the region so all real regions are finite.
    bounds = clip_geom.bounds  # (minx, miny, maxx, maxy)
    pad = max(bounds[2] - bounds[0], bounds[3] - bounds[1]) * 3.0
    cx = (bounds[0] + bounds[2]) / 2
    cy = (bounds[1] + bounds[3]) / 2
    dummies = np.array([
        [cx - pad, cy - pad],
        [cx + pad, cy - pad],
        [cx + pad, cy + pad],
        [cx - pad, cy + pad],
        [cx, cy - pad],
        [cx, cy + pad],
        [cx - pad, cy],
        [cx + pad, cy],
    ])
    all_pts = np.vstack([points_xy, dummies])
    vor = Voronoi(all_pts)

    n_real = len(points_xy)
    polys = []
    for i in range(n_real):
        region_idx = vor.point_region[i]
        region = vor.regions[region_idx]
        if -1 in region or len(region) == 0:
            # Fallback: build convex hull of nearest vertices
            verts = [vor.vertices[j] for j in region if j >= 0]
            if not verts:
                polys.append(clip_geom)
                continue
            poly = MultiPoint(verts).convex_hull
        else:
            verts = [vor.vertices[j] for j in region]
            from shapely.geometry import Polygon as _Poly
            poly = _Poly(verts)
        clipped = poly.intersection(clip_geom)
        polys.append(clipped)
    return polys


def plot_fig_voronoi_service_districts(
    journeys: pd.DataFrame,
    village_names: set[str] | None,
    *,
    infer: bool = False,
    figsize: tuple[float, float] | None = None,
) -> plt.Figure:
    """
    Choropleth map: Northwest Arctic Borough divided into approximate medevac
    service zones using Voronoi tessellation around village centroids.

    Each zone is colored by utilization rate (village→MHC legs per 1,000
    pediatric residents, 2020 Census), same colour scale as Figure 1.
    No flow lines — clean district-style layout.
    """
    import geopandas as gpd
    from shapely.geometry import Point

    if not FAC_SHP.is_file() or not BOROUGH_SHP.is_file():
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5,
                "Missing shapefiles under mapping_data/.",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return fig

    if infer:
        village_names = set(_census_village_names_excl_hub())
    elif not village_names:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "village_names required when infer=False.",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return fig

    counts = _village_to_mhc_leg_counts(journeys, village_names, infer=infer)

    # ── Load facilities, census, borough ─────────────────────────────────────
    fac = gpd.read_file(FAC_SHP)
    man_full = fac[fac["ManagingOr"] == "Maniilaq Association"].copy()
    man_full = man_full.rename(columns={"CommunityN": "NAME"})
    man_full["NAME"] = man_full["NAME"].astype(str).str.strip()
    man_full_g = gpd.GeoDataFrame(man_full, geometry="geometry",
                                   crs=fac.crs).to_crs(epsg=3338)

    names_plot = list(village_names) + ["Kotzebue"]
    man = man_full[
        man_full["NAME"].isin(names_plot) |
        man_full["NAME"].str.lower().eq("kotzebue")
    ].drop_duplicates(subset=["NAME"]).copy()
    man.loc[man["NAME"].str.lower() == "kotzebue", "NAME"] = "Kotzebue"

    pop = pd.read_csv(POP_CSV)
    man = man.merge(pop, on="NAME", how="left")
    man["medevac_count"] = man["NAME"].map(lambda n: int(counts.get(n, 0)))
    man["pediatric_pop"] = man["pediatric_pop"].fillna(
        float(man["pediatric_pop"].median())).clip(lower=1)
    man["rate_per_1k"] = (man["medevac_count"] / man["pediatric_pop"]) * 1_000.0

    man_g = gpd.GeoDataFrame(man, geometry="geometry",
                              crs=fac.crs).to_crs(epsg=3338)

    bor = gpd.read_file(BOROUGH_SHP)
    bor_ak = bor[bor["STATE"] == "02"].to_crs(epsg=3338)
    nwab = bor_ak[bor_ak["NAME"].str.contains(
        "Northwest Arctic", case=False, na=False)]

    if nwab.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "Northwest Arctic Borough not found.",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return fig

    # Include North Slope Borough so Point Hope (a Maniilaq facility located
    # in NSB) gets a real Voronoi zone rather than clipping to nothing.
    ns = bor_ak[bor_ak["NAME"].str.contains(
        "North Slope", case=False, na=False)]
    clip_boroughs = pd.concat([nwab, ns]) if not ns.empty else nwab
    borough_geom = clip_boroughs.union_all()

    # ── Voronoi zones, each clipped to its own borough ───────────────────────
    # Compute tessellation against the combined borough so zones compete across
    # the full area, then clip each zone to the borough containing its village.
    # This makes the inter-borough boundary a hard line.
    nwab_geom = nwab.union_all()
    ns_geom   = ns.union_all() if not ns.empty else None

    centroids = man_g.copy()
    centroids["_cx"] = centroids.geometry.apply(
        lambda g: float(g.x if isinstance(g, Point) else g.centroid.x))
    centroids["_cy"] = centroids.geometry.apply(
        lambda g: float(g.y if isinstance(g, Point) else g.centroid.y))

    pts = centroids[["_cx", "_cy"]].values
    raw_polys = _voronoi_polygons_clipped(pts, borough_geom)

    def _home_borough(cx: float, cy: float):
        """Return the borough geometry the village centroid falls in."""
        pt = Point(cx, cy)
        if ns_geom is not None and ns_geom.contains(pt):
            return ns_geom
        return nwab_geom

    clipped_polys = [
        poly.intersection(_home_borough(float(row["_cx"]), float(row["_cy"])))
        for poly, (_, row) in zip(raw_polys, centroids.iterrows())
    ]
    centroids["zone_geom"] = clipped_polys

    zones_gdf = gpd.GeoDataFrame(centroids, geometry="zone_geom",
                                  crs="EPSG:3338")

    # ── Colour scale ──────────────────────────────────────────────────────────
    gs_cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "reds_med", plt.get_cmap("Reds")(np.linspace(0.15, 1.0, 256)))
    colorbar_max = max(80.0,
                       float(man_g["rate_per_1k"].quantile(0.95)) + 5)
    rate_norm = mcolors.Normalize(vmin=0, vmax=colorbar_max)

    # ── Figure ────────────────────────────────────────────────────────────────
    bx0, bx1, by0, by1 = _map_bounds_manuscript(man_full_g)
    if figsize is None:
        _dw = max(bx1 - bx0, 1.0)
        _dh = max(by1 - by0, 1.0)
        _h = 9.2
        _w_map = _h * (_dw / _dh)
        _w_cbar = max(0.9, min(1.45, 0.06 * _w_map + 0.85))
        figsize = (_w_map + _w_cbar, _h + 0.95)

    fig, ax = plt.subplots(figsize=figsize)

    # Grey background for adjacent boroughs
    bor_ak.plot(ax=ax, color="lightgrey", edgecolor="black",
                alpha=0.25, linewidth=0.3)

    # Colour each village zone
    for _, row in zones_gdf.iterrows():
        rate = float(row["rate_per_1k"])
        col = gs_cmap(rate_norm(np.clip(rate, 0, colorbar_max)))
        zone = gpd.GeoDataFrame(geometry=[row["zone_geom"]], crs="EPSG:3338")
        zone.plot(ax=ax, color=col, edgecolor="white", linewidth=0.6, alpha=0.88)

    # Borough outline on top
    nwab.boundary.plot(ax=ax, edgecolor="black", linewidth=1.0)

    # ── CDP polygons overlaid as dark grey village footprints ────────────────
    if PLACES_SHP.is_file():
        cdp_all = gpd.read_file(PLACES_SHP).to_crs(epsg=3338)
        all_village_names = set(village_names) | {"Kotzebue"}
        cdp = cdp_all[cdp_all["NAME"].isin(all_village_names)].copy()
        cdp.plot(ax=ax, color="#444444", edgecolor="white",
                 linewidth=0.5, alpha=0.75, zorder=6)

    # ── Village labels offset from CDP with leader line ───────────────────────
    # Per-village label offset (dx, dy) in EPSG:3338 metres from the village
    # centroid. Default is straight up; override below for crowded villages.
    _LABEL_OFFSETS: dict[str, tuple[float, float]] = {
        "Kobuk":     ( 40_000,  10_000),
        "Point Hope": ( 35_000,   0),
        "Shungnak":  (-11_000, -22_000),   # zone rep point — inside narrow zone
        "Ambler":    (  5_000,  30_000),
        "Noorvik":   (-12_000,  22_000),   # zone rep point — above Kiana
        "Selawik":   (  5_000, -30_000),
        "Kotzebue":  ( -8_000, -25_000),
    }
    _DEFAULT_OFFSET = (0, 28_000)

    fs_village = 9
    for _, row in zones_gdf.iterrows():
        name = str(row["NAME"])
        vx, vy = float(row["_cx"]), float(row["_cy"])

        nleg = int(row["medevac_count"])
        rate = float(row["rate_per_1k"])

        is_kotzebue = name.lower() == "kotzebue"
        if is_kotzebue:
            lbl = "Maniilaq Health\nCenter (Kotzebue)"
        else:
            lbl = f"{name}\nn={nleg} ({rate:.0f}/1k)"

        dx, dy = _LABEL_OFFSETS.get(name, _DEFAULT_OFFSET)
        fw = "bold" if is_kotzebue else "normal"

        ax.annotate(
            lbl,
            xy=(vx, vy),
            xytext=(vx + dx, vy + dy),
            ha="center", va="center",
            fontsize=fs_village, fontweight=fw,
            bbox=dict(boxstyle="round,pad=0.22", facecolor="white",
                      edgecolor="0.55", alpha=0.92, linewidth=0.4),
            arrowprops=dict(arrowstyle="-", color="0.4",
                            lw=0.7, shrinkA=4, shrinkB=4),
            zorder=11,
        )

    ax.set_xlim(bx0, bx1)
    ax.set_ylim(by0, by1)
    ax.set_aspect("equal")
    ax.axis("off")

    sm = plt.cm.ScalarMappable(cmap=gs_cmap, norm=rate_norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.72, pad=0.015, aspect=22)
    cbar.set_label(
        "Medevac legs to MHC per 1,000 residents under 18 (2020 Census)",
        fontsize=12)
    cbar.ax.tick_params(labelsize=10)

    ax.set_title(
        "Figure 3. Approximate medevac service districts — pediatric utilization by village",
        fontsize=15, pad=8)

    fig.subplots_adjust(left=0.02, right=0.98, top=0.94, bottom=0.03)
    return fig


def plot_fig_cdp_choropleth(
    journeys: pd.DataFrame,
    village_names: set[str] | None,
    *,
    infer: bool = False,
    figsize: tuple[float, float] | None = None,
) -> plt.Figure:
    """
    Choropleth map using Census Designated Place (CDP) polygon boundaries.

    CDP polygons are small (~village footprint only, <1% of borough area) but
    show the actual surveyed extent of each community.  Each polygon is colored
    by utilization rate (village→MHC legs per 1,000 pediatric residents).
    """
    import geopandas as gpd
    from shapely.geometry import Point

    if not PLACES_SHP.is_file() or not BOROUGH_SHP.is_file():
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "Missing shapefiles under mapping_data/.",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return fig

    if infer:
        village_names = set(_census_village_names_excl_hub())
    elif not village_names:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "village_names required when infer=False.",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return fig

    counts = _village_to_mhc_leg_counts(journeys, village_names, infer=infer)

    # ── Load data ─────────────────────────────────────────────────────────────
    pop = pd.read_csv(POP_CSV)
    all_names = set(village_names) | {"Kotzebue"}

    places = gpd.read_file(PLACES_SHP).to_crs(epsg=3338)
    villages = places[places["NAME"].isin(all_names)].copy()
    villages = villages.merge(pop, on="NAME", how="left")
    villages["medevac_count"] = villages["NAME"].map(
        lambda n: int(counts.get(n, 0)))
    villages["pediatric_pop"] = villages["pediatric_pop"].fillna(
        float(villages["pediatric_pop"].median())).clip(lower=1)
    villages["rate_per_1k"] = (
        villages["medevac_count"] / villages["pediatric_pop"]) * 1_000.0

    bor = gpd.read_file(BOROUGH_SHP)
    bor_ak = bor[bor["STATE"] == "02"].to_crs(epsg=3338)
    nwab = bor_ak[bor_ak["NAME"].str.contains(
        "Northwest Arctic", case=False, na=False)]
    ns = bor_ak[bor_ak["NAME"].str.contains(
        "North Slope", case=False, na=False)]

    # ── Colour scale (same as other maps) ────────────────────────────────────
    gs_cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "reds_med", plt.get_cmap("Reds")(np.linspace(0.15, 1.0, 256)))
    colorbar_max = max(80.0,
                       float(villages["rate_per_1k"].quantile(0.95)) + 5)
    rate_norm = mcolors.Normalize(vmin=0, vmax=colorbar_max)

    # ── Map extent — reuse existing bounds helper via facility layer ──────────
    fac = gpd.read_file(FAC_SHP)
    man_full = fac[fac["ManagingOr"] == "Maniilaq Association"].copy()
    man_full = man_full.rename(columns={"CommunityN": "NAME"})
    man_full["NAME"] = man_full["NAME"].astype(str).str.strip()
    man_full_g = gpd.GeoDataFrame(
        man_full, geometry="geometry", crs=fac.crs).to_crs(epsg=3338)
    bx0, bx1, by0, by1 = _map_bounds_manuscript(man_full_g)

    if figsize is None:
        _dw = max(bx1 - bx0, 1.0)
        _dh = max(by1 - by0, 1.0)
        _h = 9.2
        _w_map = _h * (_dw / _dh)
        _w_cbar = max(0.9, min(1.45, 0.06 * _w_map + 0.85))
        figsize = (_w_map + _w_cbar, _h + 0.95)

    fig, ax = plt.subplots(figsize=figsize)

    # Grey background boroughs
    bor_ak.plot(ax=ax, color="lightgrey", edgecolor="black",
                alpha=0.25, linewidth=0.3)
    nwab.plot(ax=ax, color="gainsboro", edgecolor="black", linewidth=0.5)
    if not ns.empty:
        ns.plot(ax=ax, color="gainsboro", edgecolor="black", linewidth=0.5)

    # CDP polygons colored by rate
    for _, row in villages.iterrows():
        rate = float(row["rate_per_1k"])
        col = gs_cmap(rate_norm(np.clip(rate, 0, colorbar_max)))
        gpd.GeoDataFrame(geometry=[row.geometry], crs="EPSG:3338").plot(
            ax=ax, color=col, edgecolor="white", linewidth=0.8, alpha=0.92)

    # Village name labels at centroid
    fs_village = 8
    for _, row in villages.iterrows():
        name = str(row["NAME"])
        g = row.geometry
        cx = float(g.centroid.x)
        cy = float(g.centroid.y)
        nleg = int(row["medevac_count"])
        rate = float(row["rate_per_1k"])
        lbl = f"{name}\nn={nleg} ({rate:.0f}/1k)"
        fw = "bold" if name.lower() == "kotzebue" else "normal"
        ax.annotate(lbl, xy=(cx, cy),
                    xytext=(0, 6), textcoords="offset points",
                    ha="center", va="bottom",
                    fontsize=fs_village, fontweight=fw,
                    bbox=dict(boxstyle="round,pad=0.22", facecolor="white",
                              edgecolor="0.55", alpha=0.88, linewidth=0.4),
                    zorder=10)

    ax.set_xlim(bx0, bx1)
    ax.set_ylim(by0, by1)
    ax.set_aspect("equal")
    ax.axis("off")

    sm = plt.cm.ScalarMappable(cmap=gs_cmap, norm=rate_norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.72, pad=0.015, aspect=22)
    cbar.set_label(
        "Medevac legs to MHC per 1,000 residents under 18 (2020 Census)",
        fontsize=12)
    cbar.ax.tick_params(labelsize=10)

    ax.set_title(
        "Figure 3c. Pediatric medevac utilization — Census Designated Place boundaries",
        fontsize=15, pad=8)

    fig.subplots_adjust(left=0.02, right=0.98, top=0.94, bottom=0.03)
    return fig


def plot_fig1_medevac_map(
    journeys: pd.DataFrame,
    village_names: set[str] | None,
    *,
    infer: bool = False,
    figsize: tuple[float, float] | None = None,
) -> plt.Figure:
    import geopandas as gpd
    from shapely.geometry import LineString, Point

    if not FAC_SHP.is_file() or not BOROUGH_SHP.is_file():
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "Missing shapefiles under mapping_data/. Add borough + healthcare facility layers.",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_axis_off()
        return fig

    if infer:
        village_names = set(_census_village_names_excl_hub())
    elif not village_names:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "village_names required when infer=False.",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_axis_off()
        return fig

    counts = _village_to_mhc_leg_counts(journeys, village_names, infer=infer)
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
    _dw = max(bx1 - bx0, 1.0)
    _dh = max(by1 - by0, 1.0)
    _geo_aspect = _dw / _dh
    # Figure aspect ≈ map aspect so equal-aspect data fills the canvas (no huge letterboxing).
    if figsize is None:
        _h = 9.2
        _w_map = _h * _geo_aspect
        _w_cbar = max(0.9, min(1.45, 0.06 * _w_map + 0.85))
        figsize = (_w_map + _w_cbar, _h + 0.95)

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

    # ── Village dots ─────────────────────────────────────────────────────────
    for _, row in non_kot.iterrows():
        vg = row.geometry
        if not isinstance(vg, Point):
            vg = vg.centroid
        nleg = int(row["medevac_count"])
        dot_col = gs_cmap(rate_norm(np.clip(row["rate_per_1k"], colorbar_min, colorbar_max)))
        if nleg < 1:
            dot_col = (0.85, 0.85, 0.85)
        ax.scatter(
            vg.x, vg.y,
            s=marker_size(float(row["pediatric_pop"])),
            c=[dot_col],
            edgecolors="white",
            linewidths=0.8,
            zorder=10,
        )

    # Hub marker removed — Kotzebue is identified by its text label only

    ax.set_xlim(bx0, bx1)
    ax.set_ylim(by0, by1)
    ax.set_aspect("equal")

    sm = plt.cm.ScalarMappable(cmap=gs_cmap, norm=rate_norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.72, pad=0.015, aspect=22)
    cbar.set_label(
        "Medevac legs to MHC per 1,000 residents under 18 (2020 Census)",
        fontsize=fs_cbar_lbl,
    )
    cbar.ax.tick_params(labelsize=fs_cbar_tick)

    ax.set_title(
        "Figure 1. Pediatric medevac activations to Maniilaq Health Center by village clinic",
        fontsize=fs_title,
        pad=8,
    )
    ax.set_xlabel("Alaska Albers (m)", fontsize=fs_xlab)
    ax.set_ylabel("")
    ax.axis("off")

    from matplotlib.lines import Line2D

    # Legend: min / midpoint / max counts from data — linewidths match map via leg_lw()
    if len(mc_pos) == 0:
        legend_ns = [0]
    else:
        n_lo = int(mc_pos.min())
        n_hi = int(mc_pos.max())
        if n_lo == n_hi:
            legend_ns = [n_lo]
        else:
            n_mid = (n_lo + n_hi) // 2
            if n_mid <= n_lo:
                n_mid = n_lo + 1
            if n_mid >= n_hi:
                n_mid = n_hi - 1
            if n_lo < n_mid < n_hi:
                legend_ns = [n_lo, n_mid, n_hi]
            else:
                legend_ns = [n_lo, n_hi]

    leg_handles = [
        Line2D(
            [0],
            [0],
            color="0.35",
            lw=leg_lw(n),
            label=f"n = {n} medevac legs",
            solid_capstyle="round",
        )
        for n in legend_ns
    ]
    ax.legend(
        handles=leg_handles,
        loc="upper right",
        fontsize=fs_leg + 1,
        framealpha=0.95,
        title="Route volume",
        title_fontsize=fs_leg + 2,
        handlelength=5.5,
        handleheight=2.8,
        labelspacing=1.15,
        borderpad=1.15,
        handletextpad=1.4,
        borderaxespad=0.8,
    )

    fig.subplots_adjust(left=0.02, right=0.98, top=0.94, bottom=0.03)
    fig.canvas.draw()

    _EDGE_LW = 0.8
    _LABEL_GAP_PTS = 2.8

    def _scatter_r_pts(s_area: float) -> float:
        """Scatter marker radius + half edge stroke, display points."""
        return float(np.sqrt(max(s_area, 1.0) / np.pi)) + _EDGE_LW * 0.5

    def _anchor_east_of_dot(ax_, vx: float, vy: float, s_area: float) -> tuple[float, float]:
        """Left edge of text (ha=left) just outside right side of marker."""
        r = _scatter_r_pts(s_area) + _LABEL_GAP_PTS
        cx, cy = ax_.transData.transform((vx, vy))
        xd, yd = cx + r, cy
        out = ax_.transData.inverted().transform((xd, yd))
        return float(out[0]), float(out[1])

    def _anchor_along_data_y(
        ax_, vx: float, vy: float, s_area: float, sign: float
    ) -> tuple[float, float]:
        """Move from dot center along ±data Y by (r+gap) in display space."""
        r = _scatter_r_pts(s_area) + _LABEL_GAP_PTS
        p0 = np.array(ax_.transData.transform((vx, vy)))
        p1 = np.array(ax_.transData.transform((vx, vy + sign * 50_000.0)))
        u = p1 - p0
        n = float(np.linalg.norm(u)) or 1.0
        u = u / n
        out = p0 + u * r
        inv = ax_.transData.inverted().transform((float(out[0]), float(out[1])))
        return float(inv[0]), float(inv[1])

    def _anchor_southeast_of_dot(ax_, vx: float, vy: float, s_area: float) -> tuple[float, float]:
        """Top-right corner of text (ha=right, va=top) just outside SE of marker."""
        r = _scatter_r_pts(s_area) + _LABEL_GAP_PTS
        p0 = np.array(ax_.transData.transform((vx, vy)))
        ue = np.array([1.0, 0.0])
        vs = np.array([0.0, 1.0])
        u = ue + vs
        u = u / (float(np.linalg.norm(u)) or 1.0)
        out = p0 + u * r
        inv = ax_.transData.inverted().transform((float(out[0]), float(out[1])))
        return float(inv[0]), float(inv[1])

    def _edge_on_ray_to(ax_, vx: float, vy: float, tx: float, ty: float, s_area: float) -> tuple[float, float]:
        """Point on marker rim toward (tx, ty), data coords."""
        r = _scatter_r_pts(s_area) + 0.5
        p0 = np.array(ax_.transData.transform((vx, vy)))
        p1 = np.array(ax_.transData.transform((tx, ty)))
        d = p1 - p0
        L = float(np.linalg.norm(d))
        if L < 1e-9:
            d = np.array([1.0, 0.0])
            L = 1.0
        u = d / L
        out = p0 + u * r
        inv = ax_.transData.inverted().transform((float(out[0]), float(out[1])))
        return float(inv[0]), float(inv[1])

    def _push_label_outside_dot(
        ax_, vx: float, vy: float, tcx: float, tcy: float, s_area: float
    ) -> tuple[float, float]:
        """Ensure label center (tcx,tcy) is at least (r+gap) from dot in display."""
        r = _scatter_r_pts(s_area) + _LABEL_GAP_PTS
        p0 = np.array(ax_.transData.transform((vx, vy)))
        p1 = np.array(ax_.transData.transform((tcx, tcy)))
        d = p1 - p0
        L = float(np.linalg.norm(d))
        if L < r:
            u = d / (L if L > 1e-9 else 1.0) if L > 1e-9 else np.array([1.0, 0.0])
            p1 = p0 + u * r
        inv = ax_.transData.inverted().transform((float(p1[0]), float(p1[1])))
        return float(inv[0]), float(inv[1])

    # ── Village labels (anchor touches marker rim, no overlap) ───────────────
    adjustable_texts: list = []
    adjustable_anchor_x: list[float] = []
    adjustable_anchor_y: list[float] = []

    _LABEL_Z = 13

    def _txt_kwargs(ha: str, va: str) -> dict:
        return dict(
            ha=ha, va=va,
            fontsize=fs_village,
            linespacing=1.1,
            bbox=dict(
                boxstyle="round,pad=0.26",
                facecolor="white",
                edgecolor="0.55",
                alpha=1.0,
                linewidth=0.45,
            ),
            zorder=_LABEL_Z,
        )

    for _, row in non_kot.iterrows():
        name = str(row["NAME"])
        vg = row.geometry
        if not isinstance(vg, Point):
            vg = vg.centroid
        vx, vy = float(vg.x), float(vg.y)
        lbl = _village_verbose_label(row)
        s_area = float(marker_size(float(row["pediatric_pop"])))

        if name in _LABEL_FIXED_RIGHT:
            tx, ty = _anchor_east_of_dot(ax, vx, vy, s_area)
            ax.text(tx, ty, lbl, **_txt_kwargs("left", "center"))

        elif name in _LABEL_FIXED_ABOVE:
            tx, ty = _anchor_along_data_y(ax, vx, vy, s_area, +1.0)
            ax.text(tx, ty, lbl, **_txt_kwargs("center", "bottom"))

        elif name in _LABEL_FIXED_BELOW:
            tx, ty = _anchor_along_data_y(ax, vx, vy, s_area, -1.0)
            ax.text(tx, ty, lbl, **_txt_kwargs("center", "top"))

        elif name in _LABEL_FIXED_BELOW_RIGHT:
            tx, ty = _anchor_southeast_of_dot(ax, vx, vy, s_area)
            ax.text(tx, ty, lbl, **_txt_kwargs("right", "top"))

        elif name in _VILLAGE_LABEL_ABSOLUTE_OFFSET_M:
            dx, dy, ha, va = _VILLAGE_LABEL_ABSOLUTE_OFFSET_M[name]
            tcx, tcy = vx + dx, vy + dy
            tcx, tcy = _push_label_outside_dot(ax, vx, vy, tcx, tcy, s_area)
            ex, ey = _edge_on_ray_to(ax, vx, vy, tcx, tcy, s_area)
            ax.plot([ex, tcx], [ey, tcy], color="0.45", lw=0.8, alpha=0.65, zorder=6)
            ax.text(tcx, tcy, lbl, **_txt_kwargs(ha, va))

        else:
            tcx, tcy = _village_label_center_xy(vx, vy, float(hub_pt.x), float(hub_pt.y),
                                                 name, bx0, bx1, by0, by1)
            tcx, tcy = _push_label_outside_dot(ax, vx, vy, tcx, tcy, s_area)
            ex, ey = _edge_on_ray_to(ax, vx, vy, tcx, tcy, s_area)
            ax.plot([ex, tcx], [ey, tcy], color="0.45", lw=0.8, alpha=0.65, zorder=6)
            txt = ax.text(tcx, tcy, lbl, **_txt_kwargs("center", "center"))
            adjustable_texts.append(txt)
            adjustable_anchor_x.append(vx)
            adjustable_anchor_y.append(vy)

    fig.canvas.draw()

    if adjustable_texts:
        try:
            from adjustText import adjust_text

            adjust_text(
                adjustable_texts,
                x=adjustable_anchor_x,
                y=adjustable_anchor_y,
                ax=ax,
                ensure_inside_axes=True,
                expand_axes=False,
                expand=(1.12, 1.4),
                force_text=(0.25, 0.4),
                force_pull=(0.04, 0.08),
                iter_lim=350,
            )
        except (ImportError, ValueError):
            pass

    # Restore bounds (adjustText can drift them slightly)
    ax.set_xlim(bx0, bx1)
    ax.set_ylim(by0, by1)

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
            alpha=1.0,
            linewidth=0.6,
        ),
        zorder=14,
    )

    return fig
