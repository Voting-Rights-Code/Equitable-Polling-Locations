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
# The package list comes from renv.lock (the project's pinned source of
# truth) read via jsonlite::fromJSON. No hand-maintained mirror — when
# renv::snapshot() updates the lockfile, this test follows automatically.
#
# `renv` itself is pinned in renv.lock but is not currently installed in
# the container's system library (the build pipeline uses install.packages()
# against the .devcontainer/install_r_packages.R list rather than
# renv::restore()).  Filter it out until the build pipeline switches; once
# that lands the setdiff() becomes a harmless no-op.

lockfile <- jsonlite::fromJSON("renv.lock", simplifyVector = FALSE)
packages <- setdiff(names(lockfile$Packages), "renv")

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
