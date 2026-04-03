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
- Assignment: always `<-`, never `=`. Use `TRUE`/`FALSE`, never `T`/`F`.
- All `library()` calls at the top of each script. No `setwd()` — use relative paths or `here::here()`.
- This project uses data.table — use `dt[i, j, by]` idiom, not dplyr verbs. Do not mix.
- Vectorize operations; avoid explicit loops for element-wise work. Use `vapply()` over `sapply()`.
- Use `seq_along(x)` / `seq_len(n)`, never `1:length(x)`.
- NA is not NULL. Test with `is.na()`, never `x == NA`.
- Pre-allocate vectors; never grow objects in a loop.
- Lint with `lintr::lint()`. Format with `styler::style_file()`.
- No formal test suite — validation scripts in `tests/` use manual comparison.
