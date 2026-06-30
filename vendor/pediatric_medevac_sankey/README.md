# Codex Sankey figure (Figure 2)

Vendored from the standalone Codex project. The main `pediatric_data` pipeline
exports de-identified route counts and calls this script automatically.

## How the main repo uses this

1. `analysis/R/medevac_route_export.R` writes `outputs/data/fig2_medevac_routes.csv`
   (aggregate leg counts from `journeys_primary.csv`).
2. `fig2_sankey_routes()` / `save_fig2_sankey()` in `analysis/R/paper1_figures.R`
   run:

   ```bash
   RENV_PROJECT=<repo-root> Rscript scripts/medevac_sankey_manuscript.R <csv-path>
   ```

   from this directory. Primary output:
   `figures/figure4_medevac_routes_ggforce.png` (copied to
   `outputs/figures/fig2_sankey_routes.png`).

3. R packages come from the **main repo** `renv.lock` (`ggforce`, `ggalluvial`,
   `ragg`, `svglite`). Do not rely on a separate renv here.

## Manual run (PHI machine)

```bash
cd vendor/pediatric_medevac_sankey
RENV_PROJECT=/path/to/pediatric_data \
  Rscript scripts/medevac_sankey_manuscript.R /path/to/routes.csv
```

Pass either row-level (`village,mhc,receiving_facility`) or aggregate
(`leg_type,origin,destination,n_legs`) CSV. See
`docs/medevac_route_data_dictionary.md`.

Real PHI CSVs stay local; never commit them.
