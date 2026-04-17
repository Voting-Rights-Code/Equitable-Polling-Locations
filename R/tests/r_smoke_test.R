#!/usr/bin/env Rscript
#
# Smoke test: verify R and all project-required packages are loadable.
#
# Run manually (inside the dev container or a local R env):
#   Rscript R/tests/r_smoke_test.R
#
# Or via the run.py wrapper from the host (outside the container):
#   python run.py r_test
#
# This does NOT validate the analysis logic — there are no automated tests
# for the R scripts (see R/CLAUDE.md). This only confirms the R environment
# is correctly provisioned.
#
# Keep the package list in sync with .devcontainer/install_r_packages.R.

packages <- c(
    "data.table",
    "here",
    "sf",
    "ggplot2",
    "stringr",
    "plotly",
    "DBI",
    "bigrquery",
    "yaml",
    "googleCloudStorageR",
    "gargle",
    "lubridate",
    "reticulate",
    "interactions",
    "lintr",
    "styler",
    "languageserver"
)

failed <- character()
for (pkg in packages) {
    ok <- suppressPackageStartupMessages(
        requireNamespace(pkg, quietly = TRUE)
    )
    if (!ok) failed <- c(failed, pkg)
}

if (length(failed) > 0) {
    message(sprintf("FAIL: %d package(s) not loadable: %s",
                    length(failed),
                    paste(failed, collapse = ", ")))
    quit(status = 1L)
}

cat(sprintf("OK: R %s with %d packages loadable\n",
            getRversion(),
            length(packages)))
