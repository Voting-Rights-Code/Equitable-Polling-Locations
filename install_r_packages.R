#!/usr/bin/env Rscript
#
# Bulk-install the project's direct R dependencies into the current R env's
# library.  Convenience for local (non-container) R installs only.
#
# This script does NOT drive container builds — .devcontainer/run_r_install.sh
# handles those by bootstrapping renv and running renv::restore() against
# renv.lock (the canonical pinned set).
#
# Adding or updating a project R package — use the renv-native flow:
#
#   1. Rscript -e 'renv::install("pkg-name")'    # add or upgrade
#   2. Rscript -e 'renv::snapshot()'             # capture into renv.lock
#   3. Rscript R/tests/r_smoke_test.R            # smoke test reads renv.lock
#                                                  directly; no separate list
#                                                  to keep in sync
#   4. Commit renv.lock
#
# The `packages` list below is for the local-install convenience only;
# keep it loosely in sync with the project's direct deps but it is NOT
# authoritative for container builds.

options(repos = c(CRAN = "https://cloud.r-project.org"))

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
    # Linting and formatting (referenced in R/CLAUDE.md)
    "lintr",
    "styler",
    # R Language Server for IDE integration (Zed, VS Code)
    "languageserver"
)

installed <- rownames(installed.packages())
to_install <- setdiff(packages, installed)

if (length(to_install) > 0) {
    cat(sprintf("Installing %d R packages: %s\n",
                length(to_install),
                paste(to_install, collapse = ", ")))
    install.packages(
        to_install,
        Ncpus = max(1L, parallel::detectCores() - 1L)
    )
} else {
    cat("All R packages already installed\n")
}

# Verify every required package loads
failed <- character()
for (pkg in packages) {
    ok <- suppressPackageStartupMessages(
        requireNamespace(pkg, quietly = TRUE)
    )
    if (!ok) failed <- c(failed, pkg)
}

if (length(failed) > 0) {
    stop(sprintf("Failed to load R packages: %s",
                 paste(failed, collapse = ", ")))
}

cat("R setup OK — all packages loadable\n")
cat("\nIf you added or updated a package, capture it into renv.lock:\n")
cat("  Rscript -e 'renv::snapshot()'\n")
cat("...then commit renv.lock.\n")
