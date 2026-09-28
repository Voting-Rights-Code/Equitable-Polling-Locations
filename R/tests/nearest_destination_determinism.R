#!/usr/bin/env Rscript
#
# Manual verification: does associate_destinations_to_all_blocks() assign the
# same destination to the same block on every run?
#
# Run manually (inside the dev container or a local R env):
#   Rscript R/tests/nearest_destination_determinism.R
#   RUNS=20 Rscript R/tests/nearest_destination_determinism.R
#
# Why this exists. A TODO in precinct_shape_functions.r used to read:
#
#   given how the st_nearest_feature seems to assign blocks differently every
#   run, is this the right thing to do?
#
# If that were true, no rerun of the precinct pipeline could be compared
# against a previous one -- the zero-population blocks could be attributed
# differently each time, moving both a block's fill colour and the outline it
# falls inside. That would make the whole pipeline unverifiable, so #333
# treated settling it as a prerequisite rather than a follow-up.
#
# It did not reproduce: 25 runs, across the current search and a reconstruction
# of the older per-block one, with and without shuffled inputs, gave one answer.
# That is a statement about the current pipeline on current library versions.
# It says nothing about the run that produced the delivered artifacts in July
# 2026, whose sf/GEOS/s2/PROJ versions cannot be reconstructed -- a tie broken
# by feature index is exactly the kind of thing that can move with a library
# version. The TODO was removed along with the function that carried it, and
# this script is what replaces it.
#
# It runs each trial in its own R process, so nothing is carried over between
# them -- fresh memory layout, fresh RNG state, fresh GEOS/s2 state. It also
# shuffles the input rows on half the runs, since index-order tie-breaking in
# st_nearest_feature would show up as instability when the row order changes,
# and row order is exactly what differs between a CSV read and a database read.
#
# This does NOT validate the assignments themselves, only that they are stable.
# It needs a county that has been through flag_state_provided_precincts.r, so
# that block_precinct_assignment.gpkg exists.

suppressMessages({
  library(sf)
  library(data.table)
})

LOCATION <- Sys.getenv("LOCATION", "Monongalia_County_WV")
RUN_COUNT <- as.integer(Sys.getenv("RUNS", "10"))

block_assignment_path <- file.path(
  "precinct_analysis_outputs", LOCATION, "block_precinct_assignment.gpkg"
)
results_path <- file.path(
  "datasets/results", paste0(LOCATION, "_results"),
  paste0(LOCATION, "_driving_original_configs.", LOCATION,
         "_metric_driving_time_results.csv")
)

for (required in c(block_assignment_path, results_path)) {
  if (!file.exists(required)) {
    message("SKIP: ", required, " not found. ",
            "Run flag_state_provided_precincts.r for ", LOCATION, " first, ",
            "or set LOCATION to a county that has been through it.")
    quit(status = 0L)
  }
}

# one trial, as a standalone script so each runs in a clean process
trial_dir <- tempfile("determinism")
dir.create(trial_dir)
trial_script <- file.path(trial_dir, "trial.R")
writeLines(c(
  'suppressMessages({library(sf); library(data.table); library(dplyr); library(ggplot2)})',
  'source("R/result_analysis/utility_functions/precinct_shape_functions.r")',
  'args <- commandArgs(trailingOnly = TRUE)',
  'output_path <- args[1]; shuffle_seed <- as.integer(args[2])',
  sprintf('blocks <- st_read("%s", quiet = TRUE)', block_assignment_path),
  'names(blocks)[names(blocks) %in% c("geom", "geometry")] <- "block_geometry"',
  'st_geometry(blocks) <- "block_geometry"',
  sprintf('results <- fread("%s", colClasses = list(character = "id_orig"))', results_path),
  '#shuffle both inputs on the runs that ask for it',
  'if (!is.na(shuffle_seed)) {',
  '  set.seed(shuffle_seed)',
  '  blocks <- blocks[sample(nrow(blocks)), ]',
  '  results <- results[sample(nrow(results)), ]',
  '}',
  '#the solver assigns only populated blocks, so the rest arrive as NA',
  'with_destinations <- merge(',
  '  blocks, results[, .(id_orig, id_dest)],',
  '  by.x = "GEOID20", by.y = "id_orig", all.x = TRUE',
  ')',
  'associated <- associate_destinations_to_all_blocks(with_destinations)',
  'assignments <- as.data.table(st_drop_geometry(associated))[, .(GEOID20, id_dest)]',
  'setorder(assignments, GEOID20)',
  'fwrite(assignments, output_path)'
), trial_script)

cat("location:", LOCATION, "\nruns:", RUN_COUNT,
    "(every second run with shuffled input rows)\n")

assignments_per_run <- vector("list", RUN_COUNT)
for (run_index in seq_len(RUN_COUNT)) {
  output_path <- file.path(trial_dir, paste0("run_", run_index, ".csv"))
  shuffle_seed <- if (run_index %% 2 == 0) run_index else NA
  status <- system2("Rscript", c(trial_script, output_path, shuffle_seed),
                    stdout = NULL, stderr = NULL)
  if (status != 0) {
    message("FAIL: run ", run_index, " did not complete")
    quit(status = 1L)
  }
  assignments_per_run[[run_index]] <- fread(
    output_path, colClasses = c(GEOID20 = "character")
  )
  cat(".")
}
cat("\n")

baseline <- assignments_per_run[[1]]
solver_results <- fread(results_path, colClasses = list(character = "id_orig"))
fallback_count <- sum(!baseline$GEOID20 %in% solver_results$id_orig)

differing_per_run <- vapply(assignments_per_run, function(assignments) {
  nrow(baseline[assignments, on = "GEOID20"][id_dest != i.id_dest])
}, integer(1))

cat(sprintf("blocks: %d, of which %d placed by the nearest-destination search\n",
            nrow(baseline), fallback_count))

if (any(differing_per_run > 0)) {
  message(sprintf(
    "FAIL: %d of %d runs disagreed with the first (%s blocks differing). %s",
    sum(differing_per_run > 0), RUN_COUNT,
    paste(differing_per_run[differing_per_run > 0], collapse = ", "),
    "The nearest-destination search is not stable on this data -- reruns of the precinct pipeline cannot be compared."
  ))
  quit(status = 1L)
}

cat(sprintf("OK: %d runs, identical block-to-destination assignments\n", RUN_COUNT))
