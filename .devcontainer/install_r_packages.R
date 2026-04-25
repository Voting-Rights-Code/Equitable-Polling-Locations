#!/usr/bin/env Rscript
#
# Development convenience script for adding or updating R packages.
#
# This script is NOT executed during the Docker build — the Dockerfile uses
# renv::restore() from renv.lock instead, which pins exact versions. Use this
# script interactively when you need to add a new package or update existing
# ones, then regenerate renv.lock to capture the change.
#
# Workflow for adding a new R package:
#
#   1. Add it to the `packages` vector below
#   2. Run (with sudo, since the system library is root-owned):
#        sudo Rscript .devcontainer/install_r_packages.R
#   3. Update the lockfile:
#        sudo Rscript -e "renv::snapshot(library='/usr/local/lib/R/site-library', type='all', lockfile='.devcontainer/renv.lock', prompt=FALSE, force=TRUE)"
#   4. Update R/tests/r_smoke_test.R with the new package
#   5. Verify:
#        Rscript R/tests/r_smoke_test.R
#   6. Commit renv.lock, this file, and r_smoke_test.R

options(repos = c(CRAN = "https://cloud.r-project.org"))

# Clean up any stale 00LOCK-* staging directories left behind by a previous
# install that was killed mid-compile (SIGKILL / SIGTERM from a devcontainer
# timeout, window close, or Docker daemon restart). A normal compile error
# causes install.packages() to remove its own lock; a persistent 00LOCK-*
# directory means the R process was killed before it could clean up, and its
# presence blocks any retry of that package.
site_library <- .Library.site[[1L]]
stale_locks <- list.files(
    site_library,
    pattern = "^00LOCK-",
    full.names = TRUE
)
if (length(stale_locks) > 0) {
    cat(sprintf("Removing %d stale lock dir(s): %s\n",
                length(stale_locks),
                paste(basename(stale_locks), collapse = ", ")))
    unlink(stale_locks, recursive = TRUE, force = TRUE)
}

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
cat("\nNext: update renv.lock by running:\n")
cat("  sudo Rscript -e \"renv::snapshot(library='/usr/local/lib/R/site-library', type='all', lockfile='.devcontainer/renv.lock', prompt=FALSE, force=TRUE)\"\n")
