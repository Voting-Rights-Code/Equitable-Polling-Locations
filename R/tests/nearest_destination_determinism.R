#!/usr/bin/env Rscript
#
# Manual verification: does the current precinct pipeline give the same answer
# on every run? It checks two steps:
#   - associate_destinations_to_all_blocks(): the destination given to each block
#   - combine_blocks_by_destination(): the outline built for each destination
#     from that assignment, as Step 7 of extract_precincts.r builds it
#
# Run manually (inside the dev container or a local R env):
#   Rscript R/tests/nearest_destination_determinism.R
#   RUNS=20 Rscript R/tests/nearest_destination_determinism.R
#
# Why this exists. A TODO in the old precinct_shape_functions.r read:
#
#   given how the st_nearest_feature seems to assign blocks differently every
#   run, is this the right thing to do?
#
# The old pipeline was never tested against that observation, and this script
# does not test it either: it checks only the current code, on the data and
# library versions it is run with. A pass means reruns of the current pipeline
# can be compared with each other. It does not mean the TODO was wrong, and it
# says nothing about whether a delivered map can be reproduced.
#
# Each run is its own R process, so nothing carries over between runs -- memory
# layout, RNG state, GEOS/s2 state. Every second run also shuffles its input
# rows. st_nearest_feature breaks ties by candidate row order, and row order can
# differ between reads of the same data (a database query without ORDER BY
# guarantees none). In the current search, though, the candidates are
# combine_blocks_by_destination() output, which comes back sorted by destination
# whatever the input order, so the shuffle cannot reach that tie-break here. It
# reorders only the blocks being placed and the order blocks are unioned in.
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
# args: assignment output path, outline output path, shuffle seed or "none"
trial_dir <- tempfile("determinism")
dir.create(trial_dir)
trial_script <- file.path(trial_dir, "trial.R")
writeLines(c(
  'suppressMessages({library(sf); library(data.table); library(dplyr); library(ggplot2)})',
  'source("R/result_analysis/utility_functions/precinct_shape_functions.r")',
  'args <- commandArgs(trailingOnly = TRUE)',
  'assignment_path <- args[1]; outline_path <- args[2]; shuffle_arg <- args[3]',
  sprintf('blocks <- st_read("%s", quiet = TRUE)', block_assignment_path),
  'names(blocks)[names(blocks) %in% c("geom", "geometry")] <- "block_geometry"',
  'st_geometry(blocks) <- "block_geometry"',
  sprintf('results <- fread("%s", colClasses = list(character = "id_orig"))', results_path),
  '#shuffle both inputs on the runs that ask for it',
  'if (shuffle_arg != "none") {',
  '  set.seed(as.integer(shuffle_arg))',
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
  'fwrite(assignments, assignment_path)',
  '#outlines from every block, as Step 7 combines them',
  'outlines <- combine_blocks_by_destination(associated[, c("GEOID20", "id_dest")], "id_dest")',
  'st_write(outlines, outline_path, quiet = TRUE)'
), trial_script)

cat("location:", LOCATION, "\nruns:", RUN_COUNT,
    "(every second run with shuffled input rows)\n")

assignments_per_run <- vector("list", RUN_COUNT)
outlines_per_run <- vector("list", RUN_COUNT)
for (run_index in seq_len(RUN_COUNT)) {
  assignment_path <- file.path(trial_dir, paste0("assignments_", run_index, ".csv"))
  outline_path <- file.path(trial_dir, paste0("outlines_", run_index, ".gpkg"))
  # even runs shuffle, seeded by run number so each shuffle differs but can be replayed
  shuffle_arg <- if (run_index %% 2 == 0) as.character(run_index) else "none"
  status <- system2("Rscript", c(trial_script, assignment_path, outline_path, shuffle_arg),
                    stdout = NULL, stderr = NULL)
  if (status != 0) {
    message("FAIL: run ", run_index, " did not complete")
    quit(status = 1L)
  }
  assignments_per_run[[run_index]] <- fread(
    assignment_path, colClasses = c(GEOID20 = "character")
  )
  outlines <- st_read(outline_path, quiet = TRUE)
  outlines_per_run[[run_index]] <- outlines[order(outlines$id_dest), ]
  cat(".")
}
cat("\n")

baseline <- assignments_per_run[[1]]
solver_results <- fread(results_path, colClasses = list(character = "id_orig"))
fallback_count <- sum(!baseline$GEOID20 %in% solver_results$id_orig)

differing_per_run <- vapply(assignments_per_run, function(assignments) {
  nrow(baseline[assignments, on = "GEOID20"][id_dest != i.id_dest])
}, integer(1))

baseline_outlines <- outlines_per_run[[1]]
outline_differences_per_run <- vapply(outlines_per_run, function(outlines) {
  if (!identical(outlines$id_dest, baseline_outlines$id_dest)) {
    return(nrow(baseline_outlines))
  }
  # topological equality: the same shape with its vertices in a different order still matches
  same_shape <- diag(st_equals(outlines, baseline_outlines, sparse = FALSE))
  sum(!same_shape)
}, integer(1))

cat(sprintf("blocks: %d, of which %d placed by the nearest-destination search\n",
            nrow(baseline), fallback_count))
cat(sprintf("outlines: %d destinations\n", nrow(baseline_outlines)))

failed <- FALSE
if (any(differing_per_run > 0)) {
  message(sprintf(
    "FAIL: %d of %d runs disagreed with the first on block assignments (%s blocks differing).",
    sum(differing_per_run > 0), RUN_COUNT,
    paste(differing_per_run[differing_per_run > 0], collapse = ", ")
  ))
  failed <- TRUE
}
if (any(outline_differences_per_run > 0)) {
  message(sprintf(
    "FAIL: %d of %d runs disagreed with the first on outlines (%s destinations differing, or all of them if the destination sets differ).",
    sum(outline_differences_per_run > 0), RUN_COUNT,
    paste(outline_differences_per_run[outline_differences_per_run > 0], collapse = ", ")
  ))
  failed <- TRUE
}
if (failed) {
  quit(status = 1L)
}

cat(sprintf("OK: %d runs, identical block assignments and outlines\n", RUN_COUNT))
