#!/usr/bin/env Rscript
#
# Manual verification: does storage.R build the upload manifest and upload it
# the way the analysis scripts rely on? It checks:
#   - add_graph_to_graph_file_manifest(): entries are relative to the output
#     folder, keep subfolders, and one manifest holds files from one folder only
#   - add_source_to_graph_file_manifest(): a source records a repo-relative
#     origin and the object name sources/<basename>; the same source registered
#     twice is recorded once
#   - upload_graph_files_to_cloud_storage(): every graph file and source is
#     checked before the first upload, so a missing file stops the run with its
#     name and nothing partial reaches the bucket; object names equal manifest
#     entries; sources upload after the graphs; the manifest uploads last; an
#     unset STORAGE_BASE_DIR stops the run
#
# Run manually from the repo root. Inside the dev container or a local R env:
#   Rscript R/tests/storage_manifest_harness.R
# From the host:
#   docker compose -p equitable-polling-locations -f .devcontainer/docker-compose.yml \
#     run --rm app Rscript R/tests/storage_manifest_harness.R
# Each check prints PASS or FAIL. The script exits non-zero if any check failed.
#
# Why this exists. storage.R had no test when #332 shipped a manifest whose file
# names did not match the objects beside it in the bucket (#335). The checks
# here pin the behaviour #341 and #343 restored and added, so a later change to
# storage.R can be run against them in a few seconds.
#
# How it works. gcs_upload() is replaced with a stub that records every call,
# so nothing reaches Google. The files it registers are small synthetic files
# written under result_analysis_outputs/ and datasets/ and removed at the end,
# also when a check errors part way.
#
# This does NOT run Basic_analysis.r or extract_precincts.r, so it cannot catch
# a script that forgets to register a file or sets the wrong folder. It does
# NOT exercise the real upload; that was done by hand against the scratch
# bucket on 2026-08-24 (see the #341 and #343 test plans).

library(here)

source("R/result_analysis/utility_functions/storage.R")

failures <- c()
check <- function(condition, label) {
    status <- if (isTRUE(condition)) "PASS" else "FAIL"
    cat(sprintf("[%s] %s\n", status, label))
    if (!isTRUE(condition)) {
        failures <<- c(failures, label)
    }
}

# Stub the uploader. Every call is recorded in order.
uploads <- list()
gcs_upload <- function(file, bucket, name, predefinedAcl) {
    uploads[[length(uploads) + 1]] <<- list(file = file, bucket = bucket, name = name)
    invisible(TRUE)
}

# Synthetic output files under the Basic_analysis output folder, and synthetic
# input files under datasets/ to register as sources. Both folders are removed
# at the end, also when a check errors part way.
harness_dir <- "result_analysis_outputs/harness_335_tmp"
source_dir <- "datasets/harness_335_tmp_sources"
cleanup <- function() {
    unlink(harness_dir, recursive = TRUE)
    unlink(source_dir, recursive = TRUE)
}

tryCatch({
    dir.create(file.path(harness_dir, "sub"), recursive = TRUE, showWarnings = FALSE)
    dir.create(source_dir, recursive = TRUE, showWarnings = FALSE)
    writeLines("a", file.path(harness_dir, "a.png"))
    writeLines("b", file.path(harness_dir, "sub", "b.png"))
    writeLines("s1", file.path(source_dir, "distances.csv"))
    writeLines("s2", file.path(source_dir, "results.csv"))

    # --- Defaults after sourcing -----------------------------------------------
    check(is.null(STORAGE_BASE_DIR),
          "STORAGE_BASE_DIR has no default after sourcing storage.R")

    # --- Registration ---------------------------------------------------------
    clear_graph_file_manifest()
    entry_a <- add_graph_to_graph_file_manifest(file.path(harness_dir, "a.png"))
    entry_b <- add_graph_to_graph_file_manifest(file.path(harness_dir, "sub", "b.png"))
    manifest <- get_graph_file_manifest()

    check(entry_a == "harness_335_tmp/a.png", "entry is relative to the output folder")
    check(entry_b == "harness_335_tmp/sub/b.png", "entry keeps subfolders")
    check(manifest$output_tree == "result_analysis_outputs", "first file pins the output folder")

    mixed <- tryCatch(
        add_graph_to_graph_file_manifest("precinct_analysis_outputs/x.png"),
        error = function(e) conditionMessage(e)
    )
    check(grepl("already holds files from result_analysis_outputs", mixed, fixed = TRUE),
          "a file from the other folder stops the script")

    # --- Upload, all files present --------------------------------------------
    STORAGE_BUCKET <- "harness-bucket"
    STORAGE_BASE_DIR <- "equitable-polling-locations-analyses"
    CLOUD_STORAGE_ANALYSIS_NAME <- "harness"

    uploads <- list()
    result <- upload_graph_files_to_cloud_storage()
    date_stamp <- format(result$created_at, "%Y%m%d-%H%M%S")
    base_path <- paste("equitable-polling-locations-analyses", "harness", date_stamp, sep = "/")
    names_uploaded <- vapply(uploads, function(u) u$name, character(1))
    files_uploaded <- vapply(uploads, function(u) u$file, character(1))

    check(length(uploads) == 3, "two files and the manifest are uploaded")
    check(identical(names_uploaded[1:2], paste(base_path, c(entry_a, entry_b), sep = "/")),
          "object name is base path plus entry")
    check(identical(files_uploaded[1:2],
                    file.path(here(), "result_analysis_outputs", c(entry_a, entry_b))),
          "local path is the output folder plus entry")
    check(names_uploaded[3] == paste(base_path, ANALYSIS_MANIFEST, sep = "/"),
          "manifest uploads last")

    # --- Upload, one file missing ---------------------------------------------
    unlink(file.path(harness_dir, "sub", "b.png"))
    uploads <- list()
    missing <- tryCatch(upload_graph_files_to_cloud_storage(), error = function(e) conditionMessage(e))

    check(is.character(missing) && grepl("cannot find", missing, fixed = TRUE),
          "a missing file stops the upload")
    check(is.character(missing) && grepl("sub/b.png", missing, fixed = TRUE),
          "the stop names the missing file")
    check(length(uploads) == 0, "nothing is uploaded before the missing-file stop")

    # --- Upload, STORAGE_BASE_DIR unset ---------------------------------------
    writeLines("b", file.path(harness_dir, "sub", "b.png"))
    STORAGE_BASE_DIR <- NULL
    uploads <- list()
    unset <- tryCatch(upload_graph_files_to_cloud_storage(), error = function(e) conditionMessage(e))

    check(is.character(unset) && grepl("STORAGE_BASE_DIR is not set", unset, fixed = TRUE),
          "an unset STORAGE_BASE_DIR stops with the new message")
    check(length(uploads) == 0, "nothing is uploaded when STORAGE_BASE_DIR is unset")

    # --- Sources, all present -------------------------------------------------
    clear_graph_file_manifest()
    entry_a <- add_graph_to_graph_file_manifest(file.path(harness_dir, "a.png"))
    source_1 <- add_source_to_graph_file_manifest("driving_distances", file.path(source_dir, "distances.csv"))
    source_2 <- add_source_to_graph_file_manifest("optimization_results", file.path(source_dir, "results.csv"))
    # registering the same origin twice must not add a second entry
    add_source_to_graph_file_manifest("driving_distances", file.path(source_dir, "distances.csv"))

    check(source_1$object_name == "sources/distances.csv", "source object name is sources/<basename>")
    check(source_1$origin == file.path(source_dir, "distances.csv"), "source origin is repo-relative")
    check(length(get_graph_file_manifest()$sources) == 2, "a source registered twice is recorded once")

    STORAGE_BASE_DIR <- "precinct-distance-analyses"
    uploads <- list()
    result <- upload_graph_files_to_cloud_storage()
    date_stamp <- format(result$created_at, "%Y%m%d-%H%M%S")
    base_path <- paste("precinct-distance-analyses", "harness", date_stamp, sep = "/")
    names_uploaded <- vapply(uploads, function(u) u$name, character(1))
    files_uploaded <- vapply(uploads, function(u) u$file, character(1))

    check(length(uploads) == 4, "one graph, two sources and the manifest are uploaded")
    check(identical(names_uploaded[2:3],
                    paste(base_path, c("sources/distances.csv", "sources/results.csv"), sep = "/")),
          "sources upload after the graphs under sources/<basename>")
    check(identical(files_uploaded[2:3],
                    file.path(here(), source_dir, c("distances.csv", "results.csv"))),
          "source local path is the repo root plus origin")
    check(names_uploaded[4] == paste(base_path, ANALYSIS_MANIFEST, sep = "/"),
          "manifest uploads last when sources are present")

    # --- Sources, one missing -------------------------------------------------
    unlink(file.path(source_dir, "results.csv"))
    uploads <- list()
    missing_source <- tryCatch(upload_graph_files_to_cloud_storage(), error = function(e) conditionMessage(e))

    check(is.character(missing_source) && grepl("cannot find", missing_source, fixed = TRUE),
          "a missing source stops the upload")
    check(is.character(missing_source) && grepl("results.csv", missing_source, fixed = TRUE),
          "the stop names the missing source")
    check(length(uploads) == 0, "nothing is uploaded before the missing-source stop")
}, finally = cleanup())

# --- Summary ------------------------------------------------------------------
cat(sprintf("\n%d checks failed\n", length(failures)))
if (length(failures) > 0) {
    quit(status = 1)
}
