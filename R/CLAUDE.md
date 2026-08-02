# R Analysis — Conventions

Result analysis and visualization scripts. Secondary to the Python solver — used for analyzing and mapping optimization results.

## Structure

| Directory | Purpose |
|-----------|---------|
| `result_analysis/scripts/` | Core pipeline scripts (`Basic_analysis.r`, `extract_city.r`, `extract_precincts.r`, `flag_state_provided_precincts.r`) |
| `result_analysis/precinct_configs/` | Per-county config files for the precinct-reconciliation pipeline |
| `result_analysis/city_configs/` | Per-city config files for the city-extraction pipeline |
| `result_analysis/Basic_analysis_configs/` | Per-config-set config files for `Basic_analysis.r` |
| `result_analysis/WV_state_file_corrections/` | Persistent per-county reconciliation scripts (human-reviewed corrections) |
| `result_analysis/utility_functions/` | Shared functions: storage, graphs, maps, config loading |
| `result_analysis/deprecated/` | Archived historical analyses |
| `tests/` | Manual verification scripts (not automated) |

Key libraries: `data.table`, `ggplot2`, `sf`, `bigrquery`, `googleCloudStorageR`, `yaml`, `plotly`. No formal R package structure — standalone analysis scripts.

## Conventions

- Follow the tidyverse style guide. Use `snake_case` for all names. Files: `snake_case.R`.
- Assignment: Preferentially use `<-`. Only use `=` when `<-` will cause an error (E.g. when using named variables). 
- Use `TRUE`/`FALSE`, never `T`/`F`.
- All `library()` calls at the top of each script. 
- Never use `setwd()` in a way that will not transfer across different users or different machines or different copies of the program in the same machine.
- This project uses data.table — use `dt[i, j, by]` idiom. Only use dplyr verbs when there is no way to perform the action using data.table.
  - Exception: for `sf` objects, prefer `dplyr::group_by()`/`summarise()` (sf-aware) or base `sf`/`split()`+`lapply()` over `data.table`'s grouping or `merge()` for any step that must preserve `sfc` attributes (`crs`, `bbox`, `precision`). `data.table` operations on geometry list-columns silently strip these even though `class()` still reports `sfc`, breaking later `st_area()`/`st_sym_difference()` calls with cryptic type errors.
- Vectorize operations; avoid explicit loops for element-wise work. 
- Use `seq_along(x)` / `seq_len(n)`, never `1:length(x)`.
- NA is not NULL. Test with `is.na()` or `is.null()`, never `x == NA` or `x == NULL`.
- Pre-allocate vectors; never grow objects in a loop.
- Lint with `lintr::lint()`. Format with `styler::style_file()`.
- No formal test suite.


### Comments

Guiding question: what would someone need to pick this code up and contribute to it? Answer it as tersely as the altitude allows — three layers, not one.

- **Script sections** (`Step 1: ...`, `#######` banners) group a *sequence* of function calls in a linear, top-to-bottom script (`extract_precincts.r`, `flag_state_provided_precincts.r`) into named phases. Only earns its keep when there's an actual sequence to narrate — utility files whose functions get called from elsewhere in arbitrary order don't need it.
- **Function headers** carry the *why* — a few sentences above the function: what problem it solves, why it exists, why it's shaped the way it is. Allowed to run more than one line.
- **Internal comments** are bare scaffolding: one short phrase per logical block, description not explanation. Their job is letting a reader check the code against the header's claim at a skim, not re-explaining it. Give one its own "why" clause only when that specific step hides something the header didn't cover (`put in empty columns... so bg_data can drop them cleanly`) — that's the exception, not the default.

Cut a cross-reference to another function when it only claims "this works like that" (`mirrors color_bounds`) — useful once, dead weight after. Keep one when it cites where an unusual technique's precedent lives (`as in make_precinct_maps`).

## Package Management

R packages are managed by [renv](https://rstudio.github.io/renv/). `renv.lock` at the repo root is the canonical pinned package set. To add or update a package, use `renv::install("pkg-name")` followed by `renv::snapshot()`, then commit `renv.lock`. The smoke test (`R/tests/r_smoke_test.R`) reads from `renv.lock` directly — no separate list to keep in sync.
