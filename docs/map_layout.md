# Map layout: bounds and labels (Figure 1)

## Bounds

| Approach | When to use |
|----------|-------------|
| **Referenced (preferred)** | Tie `xmin` / `xmax` / `ymin` / `ymax` to **named places** plus fixed offsets in the map CRS (here EPSG:3338, meters). If facility coordinates update, the frame moves consistently. Implemented in `_map_bounds_manuscript()` in `analysis/medevac_map_fig1.py`. |
| **Hard-coded axis limits** | Only for quick fixes or exports that must match an exact prior figure. Document why and the date. |
| **External config (YAML/JSON)** | Optional if non-coders need to tweak framing without editing Python. Same logic reads numeric offsets from file. |

Keep a short comment in code listing anchor communities and offset sizes (e.g. “Point Hope −50 km west”).

## Labels

| Layer | Practice |
|-------|----------|
| **Villages** | Label center in **map meters** (EPSG:3338): from each village, offset **along** the ray Kotzebue→village (away from hub) plus **perpendicular** meters (`_VILLAGE_LABEL_ALONG_PERP_M`) so neighbors separate. **No leader lines.** Edit that dict to nudge any crowded pair. |
| **Hub (MHC)** | Single `annotate` with offset points; adjust if legend/colorbar collide. |
| **Borough / large regions** | **Geometry + viewport**: intersect borough polygon with the **same map rectangle** used for `set_xlim` / `set_ylim`, then place text at `representative_point()` of the **largest visible fragment**. Optional meter nudges: `_BOROUGH_LABEL_OFFSET_M` in `medevac_map_fig1.py` (east, north in EPSG:3338). |

## Single source of truth

Compute map bounds **once** per figure (`bx0, bx1, by0, by1`) and reuse for:

1. Borough label placement (intersection with view),
2. `set_xlim` / `set_ylim`.

That keeps labels aligned with the visible grey basemap.
