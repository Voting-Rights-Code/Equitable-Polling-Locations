# R Analysis — Conventions

Result analysis and visualization scripts. Secondary to the Python solver — used for analyzing and mapping optimization results.

## Structure

| Directory | Purpose |
|-----------|---------|
| `result_analysis/` | Main analysis scripts (per-county configs) |
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
- Vectorize operations; avoid explicit loops for element-wise work. 
- Use `seq_along(x)` / `seq_len(n)`, never `1:length(x)`.
- NA is not NULL. Test with `is.na()` or `is.null()`, never `x == NA` or `x == NULL`.
- Pre-allocate vectors; never grow objects in a loop.
- Lint with `lintr::lint()`. Format with `styler::style_file()`.
- No formal test suite.

## Package Management

R packages are managed by [renv](https://rstudio.github.io/renv/). `renv.lock` at the repo root is the canonical pinned package set. To add or update a package, use `renv::install("pkg-name")` followed by `renv::snapshot()`, then commit `renv.lock`. The smoke test (`R/tests/r_smoke_test.R`) reads from `renv.lock` directly — no separate list to keep in sync.
