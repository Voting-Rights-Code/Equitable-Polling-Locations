#!/usr/bin/env Rscript
#
# Manual verification: does storage.R build the upload manifest and upload it
# the way the analysis scripts rely on? It checks:
#   - add_graph_to_graph_file_manifest(): entries are relative to the output
#     folder, keep subfolders, and one manifest holds files from one folder only
#   - add_source_to_graph_file_manifest(): a source records a repo-relative
#     origin and, when git does not track it, the object name sources/<basename>;
#     the same source registered twice is recorded once
#   - upload_graph_files_to_cloud_storage(): every graph file and source is
#     checked before the first upload, so a missing file stops the run with its
#     name and nothing partial reaches the bucket; object names equal manifest
#     entries; sources upload after the graphs; the manifest uploads last; an
#     unset STORAGE_BASE_DIR stops the run; authentication happens once, after
#     the existence checks and before the first upload
#   - CLOUD_STORAGE_DELIVERABLE: has no default after sourcing; when set, object
#     names and the manifest object follow base folder, analysis name,
#     deliverable, datestamp; the manifest records `deliverable` when set and
#     has no such field when unset; a value that is not one path segment (e.g.
#     with a slash) or not a string stops the run before anything authenticates
#     or uploads
#   - input kinds: an input in git with no change is recorded as `git`, with the
#     commit of the run, and is not uploaded; an untracked input is recorded as
#     `upload` and uploaded; a modified input stops the run and is named, unless
#     ALLOW_UNCOMMITTED_SOURCES is TRUE; a census input records its location and
#     an integer census_year, makes no git call and is not uploaded; a
#     census_year that is not one whole number stops; an untracked folder stops;
#     a manifest with no `git` input has no `commit` field; a commit that moved
#     during the run stops the upload before authentication
#   - the real git functions: an untracked file that .gitignore ignores is
#     `untracked`, and a folder that is not a git checkout stops
#   - set_cloud_storage_deliverable(): an unknown name stops, is named and sets
#     nothing; a known name sets CLOUD_STORAGE_DELIVERABLE; the upload rejects
#     an unknown name that was assigned directly
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
# How it works. gcs_upload() and authenticate_cloud_storage() are replaced with
# stubs that record every call, so nothing reaches Google and no credentials are
# needed. get_git_source_status() and get_git_head_commit() are stubbed too, so
# the checks do not depend on the state of this checkout; the two checks of the
# real git functions need git, git-lfs and a git checkout. The files it registers
# are small synthetic files written under result_analysis_outputs/ and datasets/
# and removed at the end, also when a check errors part way.
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

# Stub the uploader and the authenticator. Every call is recorded in order, and
# `events` keeps the relative order of authentication and uploads.
uploads <- list()
events <- character(0)
gcs_upload <- function(file, bucket, name, predefinedAcl) {
    uploads[[length(uploads) + 1]] <<- list(file = file, bucket = bucket, name = name)
    events[length(events) + 1] <<- "upload"
    invisible(TRUE)
}
authenticate_cloud_storage <- function() {
    events[length(events) + 1] <<- "auth"
    invisible(TRUE)
}

# Stub the two git functions and record each call. The real ones are kept for the
# two checks of git itself. Inputs are untracked unless a check says otherwise.
real_get_git_source_status <- get0("get_git_source_status")
real_get_git_head_commit <- get0("get_git_head_commit")
stub_source_status <- "untracked"
stub_head_commit <- "0123456789abcdef0123456789abcdef01234567"
git_calls <- character(0)
get_git_source_status <- function(origin, root = here()) {
    git_calls[length(git_calls) + 1] <<- "source_status"
    stub_source_status
}
get_git_head_commit <- function(root = here()) {
    git_calls[length(git_calls) + 1] <<- "head_commit"
    stub_head_commit
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

# The value of expr, or its error message. A stop, or a call to something that
# does not exist, then prints FAIL instead of ending the harness.
attempt <- function(expr) tryCatch(expr, error = function(e) conditionMessage(e))

# A new manifest with the one graph file an upload needs, and empty call records
start_manifest <- function() {
    clear_graph_file_manifest()
    add_graph_to_graph_file_manifest(file.path(harness_dir, "a.png"))
    uploads <<- list()
    events <<- character(0)
    git_calls <<- character(0)
}

# The recorded source, or an empty list when there is not exactly one
only_source <- function() {
    sources <- get_graph_file_manifest()$sources
    if (length(sources) == 1) sources[[1]] else list()
}

uploaded_names <- function() vapply(uploads, function(u) u$name, character(1))

# The YAML of the last upload, which is the manifest when an upload completes
written_manifest <- function() {
    if (length(uploads) == 0) {
        return("")
    }
    paste(readLines(uploads[[length(uploads)]]$file), collapse = "\n")
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
    check(is.null(CLOUD_STORAGE_DELIVERABLE),
          "CLOUD_STORAGE_DELIVERABLE has no default after sourcing storage.R")

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
    events <- character(0)
    result <- upload_graph_files_to_cloud_storage()
    date_stamp <- format(result$created_at, "%Y%m%d-%H%M%S")
    base_path <- paste("equitable-polling-locations-analyses", "harness", date_stamp, sep = "/")
    names_uploaded <- vapply(uploads, function(u) u$name, character(1))
    files_uploaded <- vapply(uploads, function(u) u$file, character(1))

    check(length(uploads) == 3, "two files and the manifest are uploaded")
    check(length(events) > 0 && events[1] == "auth" && sum(events == "auth") == 1,
          "authentication happens once, before the first upload")
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
    events <- character(0)
    missing <- tryCatch(upload_graph_files_to_cloud_storage(), error = function(e) conditionMessage(e))

    check(is.character(missing) && grepl("cannot find", missing, fixed = TRUE),
          "a missing file stops the upload")
    check(is.character(missing) && grepl("sub/b.png", missing, fixed = TRUE),
          "the stop names the missing file")
    check(length(uploads) == 0, "nothing is uploaded before the missing-file stop")
    check(sum(events == "auth") == 0, "nothing authenticates before the missing-file stop")

    # --- Upload, STORAGE_BASE_DIR unset ---------------------------------------
    writeLines("b", file.path(harness_dir, "sub", "b.png"))
    STORAGE_BASE_DIR <- NULL
    uploads <- list()
    events <- character(0)
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
    events <- character(0)
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
    events <- character(0)
    missing_source <- tryCatch(upload_graph_files_to_cloud_storage(), error = function(e) conditionMessage(e))

    check(is.character(missing_source) && grepl("cannot find", missing_source, fixed = TRUE),
          "a missing source stops the upload")
    check(is.character(missing_source) && grepl("results.csv", missing_source, fixed = TRUE),
          "the stop names the missing source")
    check(length(uploads) == 0, "nothing is uploaded before the missing-source stop")

    # --- Deliverable folder ---------------------------------------------------
    clear_graph_file_manifest()
    entry_a <- add_graph_to_graph_file_manifest(file.path(harness_dir, "a.png"))
    STORAGE_BASE_DIR <- "precinct-distance-analyses"
    CLOUD_STORAGE_DELIVERABLE <- "distance_analysis"
    uploads <- list()
    events <- character(0)
    with_deliverable <- upload_graph_files_to_cloud_storage()
    date_stamp <- format(with_deliverable$created_at, "%Y%m%d-%H%M%S")
    deliverable_path <- paste("precinct-distance-analyses", "harness", "distance_analysis",
                              date_stamp, sep = "/")
    names_uploaded <- vapply(uploads, function(u) u$name, character(1))

    check(identical(names_uploaded[1], paste(deliverable_path, entry_a, sep = "/")),
          "with a deliverable, the object name is base folder, analysis name, deliverable, datestamp, entry")
    check(identical(names_uploaded[length(names_uploaded)],
                    paste(deliverable_path, ANALYSIS_MANIFEST, sep = "/")),
          "with a deliverable, the manifest uploads under the same four-part path")

    # The same registered manifest, uploaded again with the deliverable unset
    CLOUD_STORAGE_DELIVERABLE <- NULL
    without_deliverable <- upload_graph_files_to_cloud_storage()
    check(identical(with_deliverable$deliverable, "distance_analysis") &&
              !("deliverable" %in% names(without_deliverable)),
          "the manifest records the deliverable when set and has no deliverable field when unset")

    # A value that is not one path segment stops the run before any upload
    CLOUD_STORAGE_DELIVERABLE <- "distance/analysis"
    uploads <- list()
    events <- character(0)
    bad_deliverable <- tryCatch(upload_graph_files_to_cloud_storage(), error = function(e) conditionMessage(e))
    check(is.character(bad_deliverable) && grepl("distance/analysis", bad_deliverable, fixed = TRUE) &&
              length(uploads) == 0,
          "a deliverable with a slash stops the upload before any object is uploaded")
    check(sum(events == "auth") == 0, "nothing authenticates before the bad-deliverable stop")

    # A value that is not a string stops with the same message, not an R error
    CLOUD_STORAGE_DELIVERABLE <- 5
    uploads <- list()
    events <- character(0)
    numeric_deliverable <- tryCatch(upload_graph_files_to_cloud_storage(), error = function(e) conditionMessage(e))
    check(is.character(numeric_deliverable) &&
              grepl("Invalid CLOUD_STORAGE_DELIVERABLE", numeric_deliverable, fixed = TRUE) &&
              length(uploads) == 0,
          "a non-character deliverable stops with the invalid-deliverable message before any upload")

    # Later checks expect three-part paths
    CLOUD_STORAGE_DELIVERABLE <- NULL

    # --- Input kinds ------------------------------------------------------------
    input_path <- file.path(source_dir, "distances.csv")

    stub_source_status <- "clean"
    start_manifest()
    attempt(add_source_to_graph_file_manifest("driving_distances", input_path))
    result <- attempt(upload_graph_files_to_cloud_storage())
    check(identical(only_source()$kind, "git") && is.null(only_source()$object_name) &&
              length(uploads) == 2 && !any(grepl("sources/", uploaded_names(), fixed = TRUE)),
          "a clean input is recorded as git with no object_name and is not uploaded")
    check(is.list(result) && identical(result$commit, stub_head_commit) &&
              grepl(paste0("commit: ", stub_head_commit), written_manifest(), fixed = TRUE),
          "the manifest commit is the commit of the checkout")

    stub_source_status <- "untracked"
    start_manifest()
    attempt(add_source_to_graph_file_manifest("driving_distances", input_path))
    attempt(upload_graph_files_to_cloud_storage())
    check(identical(only_source()$kind, "upload") &&
              identical(only_source()$object_name, "sources/distances.csv") &&
              any(endsWith(uploaded_names(), "/sources/distances.csv")),
          "an untracked input is recorded as upload and uploaded under sources/<basename>")

    stub_source_status <- "modified"
    start_manifest()
    modified <- attempt(add_source_to_graph_file_manifest("driving_distances", input_path))
    check(is.character(modified) && grepl("uncommitted change", modified, fixed = TRUE) &&
              grepl(input_path, modified, fixed = TRUE) &&
              length(get_graph_file_manifest()$sources) == 0,
          "a modified input stops at registration and the message names it")

    ALLOW_UNCOMMITTED_SOURCES <- TRUE
    start_manifest()
    attempt(add_source_to_graph_file_manifest("driving_distances", input_path))
    result <- attempt(upload_graph_files_to_cloud_storage())
    check(identical(only_source()$kind, "git") && isTRUE(only_source()$uncommitted) &&
              is.null(only_source()$object_name) && length(uploads) == 2 &&
              is.list(result) && identical(result$commit, stub_head_commit) &&
              grepl("uncommitted: true", written_manifest(), fixed = TRUE),
          "ALLOW_UNCOMMITTED_SOURCES records a modified input as uncommitted git, not uploaded")
    ALLOW_UNCOMMITTED_SOURCES <- FALSE

    start_manifest()
    attempt(add_census_source_to_graph_file_manifest("census_p3", input_path, "Harness_County_XX", 2020))
    attempt(upload_graph_files_to_cloud_storage())
    check(identical(only_source()$kind, "census") &&
              identical(only_source()$location, "Harness_County_XX") &&
              identical(only_source()$census_year, 2020L) &&
              is.null(only_source()$object_name) && length(uploads) == 2 &&
              grepl("census_year: 2020(\n|$)", written_manifest()) &&
              length(git_calls) == 0,
          "a census input records location and integer census_year, with no upload or git call")

    start_manifest()
    year_results <- lapply(list("2020", c(2010, 2020), 2020.5), function(census_year) {
        attempt(add_census_source_to_graph_file_manifest("census_p3", input_path,
                                                         "Harness_County_XX", census_year))
    })
    check(all(vapply(year_results, function(year_result) {
              is.character(year_result) && grepl("census_year", year_result, fixed = TRUE)
          }, logical(1))) &&
              length(get_graph_file_manifest()$sources) == 0,
          "a census_year that is not one whole number stops at registration")

    stub_source_status <- "untracked"
    start_manifest()
    attempt(add_source_to_graph_file_manifest("driving_distances", input_path))
    result <- attempt(upload_graph_files_to_cloud_storage())
    check(identical(only_source()$kind, "upload") && is.list(result) &&
              !("commit" %in% names(result)) && !grepl("(^|\n)commit:", written_manifest()),
          "a manifest with only upload inputs has no commit field")

    stub_source_status <- "clean"
    start_manifest()
    attempt(add_source_to_graph_file_manifest("driving_distances", input_path))
    recorded_commit <- stub_head_commit
    stub_head_commit <- "fedcba9876543210fedcba9876543210fedcba98"
    moved <- attempt(upload_graph_files_to_cloud_storage())
    check(is.character(moved) && grepl(recorded_commit, moved, fixed = TRUE) &&
              grepl(stub_head_commit, moved, fixed = TRUE) && length(events) == 0,
          "a commit that moved during the run stops the upload before authentication")
    stub_head_commit <- recorded_commit

    folder_path <- file.path(source_dir, "precinct_shapes")
    dir.create(folder_path, showWarnings = FALSE)
    writeLines("s3", file.path(folder_path, "precincts.shp"))
    stub_source_status <- "untracked"
    start_manifest()
    untracked_folder <- attempt(add_source_to_graph_file_manifest("state_precincts", folder_path))
    check(is.character(untracked_folder) &&
              grepl("cannot upload a folder", untracked_folder, fixed = TRUE) &&
              grepl(folder_path, untracked_folder, fixed = TRUE) &&
              length(get_graph_file_manifest()$sources) == 0,
          "an untracked folder stops at registration")

    # The real git functions. .gitignore ignores *.csv, and `git status` alone
    # prints nothing for an ignored file that is not tracked.
    ignore_status <- system2("git", c("-C", shQuote(here()), "check-ignore", "-q", "--",
                                      shQuote(input_path)))
    real_status <- attempt(real_get_git_source_status(input_path))
    check(ignore_status == 0 && identical(real_status, "untracked"),
          "the real get_git_source_status() calls an ignored, untracked CSV untracked")

    non_checkout <- tempfile("not_a_git_checkout_")
    dir.create(non_checkout)
    no_checkout <- attempt(real_get_git_head_commit(non_checkout))
    unlink(non_checkout, recursive = TRUE)
    check(grepl("git cannot answer", no_checkout, fixed = TRUE) &&
              grepl(non_checkout, no_checkout, fixed = TRUE),
          "the real get_git_head_commit() stops outside a git checkout")

    # --- Deliverable allowlist --------------------------------------------------
    unknown_name <- attempt(set_cloud_storage_deliverable("distanec_analysis"))
    check(is.character(unknown_name) && grepl("distanec_analysis", unknown_name, fixed = TRUE) &&
              grepl("flagged_precincts", unknown_name, fixed = TRUE) &&
              is.null(CLOUD_STORAGE_DELIVERABLE),
          "set_cloud_storage_deliverable() stops on an unknown name and sets nothing")

    attempt(set_cloud_storage_deliverable("distance_analysis"))
    check(identical(CLOUD_STORAGE_DELIVERABLE, "distance_analysis"),
          "set_cloud_storage_deliverable() sets CLOUD_STORAGE_DELIVERABLE to a known name")

    # Assigned directly, past set_cloud_storage_deliverable()
    CLOUD_STORAGE_DELIVERABLE <- "distanec_analysis"
    start_manifest()
    assigned_name <- attempt(upload_graph_files_to_cloud_storage())
    check(is.character(assigned_name) &&
              grepl("Invalid CLOUD_STORAGE_DELIVERABLE 'distanec_analysis'", assigned_name,
                    fixed = TRUE) &&
              length(events) == 0,
          "an unknown name assigned directly stops the upload before authentication")
    CLOUD_STORAGE_DELIVERABLE <- NULL
}, finally = cleanup())

# --- Summary ------------------------------------------------------------------
cat(sprintf("\n%d checks failed\n", length(failures)))
if (length(failures) > 0) {
    quit(status = 1)
}
