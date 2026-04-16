#!/usr/bin/env Rscript
#
# Install R packages required by the R/ analysis toolkit.
#
# Invoked at image build time from .devcontainer/Dockerfile (running as root
# so /usr/local/lib/R/site-library is writable). Keeping the package list here
# (not in environment.yml, which is conda-only) is the single source of truth
# for R deps inside the dev container. Packages are installed from CRAN source;
# build tooling and system libs (libgdal-dev, libcurl4-openssl-dev, etc.) come
# from the apt install earlier in the Dockerfile.
#
# All of these are active dependencies in R/result_analysis/ and R/tests/;
# deprecated scripts in R/result_analysis/deprecated/ are intentionally
# excluded.

# Set an explicit CRAN mirror. In a non-interactive Docker build R has no
# stdin to prompt the user for a mirror, and some installs will hang or
# silently pick an outdated default. cloud.r-project.org is CRAN's official
# global CDN.
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
    "styler"
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

# Verify every required package loads. This is the smoke test that runs on
# every container build — a broken install fails the devcontainer build
# rather than leaving a subtly-broken env for someone to discover later.
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
