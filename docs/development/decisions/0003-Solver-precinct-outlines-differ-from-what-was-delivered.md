# 0003: Solver precinct outlines differ from what was delivered — now built entirely within the precinct_analysis pipeline, not from Basic_analysis.r's outputs

## Status

Accepted

## Context

### How the delivered maps were built

The solver-assignment heat maps delivered for Monongalia County were assembled from two
scripts, run in sequence, each supplying half of the image.

The shapefile, or outline, came from `Basic_analysis.r`, run for the county and config. It
called `make_precinct_map()`, which wrote `<location>_precinct_<descriptor>.shp` — the
dissolved polygons defining optimized precincts, showing which populated blocks the solver
assigned to the same destination, with non-populated blocks assigned by dissolving into an
adjacent geometry.

Then `extract_precincts.r` assigned each non-populated block to a single arbitrary
destination. In Step 7 it read `Basic_analysis.r`'s shapefile back through `get_solver_precinct_shapes()`,
pointed at it by the `SOLVER_PRECINCT_SHAPEFILE` entry in the county config.
`make_demo_distance_heat_map()` takes the fill data from `extract_precincts.r` and the
outline geometry from `Basic_analysis.r` as separate arguments, combining the two pipelines.

A staleness check in `get_solver_precinct_shapes()` compared the shapefile's mtime against
the results file's and stopped if the shapefile was older. The county config carried a
matching warning to "rerun that script for this county/config if `OPTIMIZATION_RESULTS` changes, to keep this
in sync."

### Why that was a problem

Each pipeline assigned non-populated blocks differently. Furthermore, due to a possible
non-determinism of `st_nearest_feature`, the assignment in the `Basic_analysis.r` pipeline
was not consistent.

When those assignments disagreed, a block was filled with one destination's colour while
sitting inside a different destination's outline. That is a wrong answer in a delivered map,
and nothing in the data flags it: both halves are internally consistent, the mtime guard
passes, and the disagreement is visible only by looking at the picture. The staleness check
catches an out-of-date file; it cannot catch two live computations differing.

### Why the previous arrangement could not be patched

Three attempts were considered against the delivered structure, and each failed on
something about that structure rather than on effort.

1. Sharing the unpopulated block assignment as a common function — the shape of PR #330 — is
not enough, because the two callers search against different candidate geometry: individual
assigned blocks on one side, already-dissolved per-destination polygons on the other.
Identical code over different candidates gives different answers. On Monongalia it gives 55
of them (see "Measured, for Monongalia" below) from the current pipeline. Sharing the code
without also fixing the possible non-determinism leaves the defect in place.

Furthermore, in previous implementations, `st_nearest_feature` had some non-determinism in
it, which led to a now removed comment in `precinct_shape_functions.r` recording that
`st_nearest_feature` "seems to assign blocks differently every run". There
is also undocumented evidence of this variation in deliveries to Bartow county. However,
this new pipeline for precinct maps seems to have removed this non-determinism in both the
precinct map generation and the assignment needed for Monongalia county.

2. Having `make_precinct_map()` hand its per-block assignment to the flagging path is blocked
by the function's own internals. The block identifier is destroyed before the unpopulated
block assignment runs: the populated blocks are collapsed by `summarize()`, and the
unpopulated side is then narrowed to those same columns before the `st_join`. There is no per-block table at that
point to hand over, and producing one means restructuring the function and making a plotting
routine responsible for returning data.

Reconciling after the fact — inferring assignment by containment against the written
shapefile — is a possible mitigation. But it derives the answer from a picture of the
answer, which only works while the shapefile is current, and it keeps the cross-script,
cross-run dependency bound by a weak staleness check.

## Decision

`extract_precincts.r` produces the solver precinct outline itself, from its own data, and
stops reading anything `Basic_analysis.r` wrote. There is no longer a dependence on the
precinct shapes produced by `Basic_analysis.r`. `get_solver_precinct_shapes()`, its mtime
guard, and the `SOLVER_PRECINCT_SHAPEFILE` config entry are removed.

The outline is built by first assigning each block to a destination, with empty blocks
assigned to their nearest neighbor. This is computed once per run and shared by each
`solver_distance_flagged_blocks_*`, which joins the assignment to distances to give the
fill. The outline is drawn by dissolving the assignment against `block_precinct_assignment`
geometry. The outline and the fill are made from the same, single assignment, and cannot
disagree.

Additionally, `make_precinct_map()` is refactored into `map_functions.R` as a composition of
a combining function and an assigning function:

- `combine_blocks_by_destination()` — deterministic. A per-block table plus geometry to one
  polygon per destination.
- `associate_destinations_to_all_blocks()` — possibly non-deterministic. Every block to a
  destination, including the unpopulated blocks.

Combining is the primitive and associating is layered on it, because the better
nearest-neighbour search is against combined per-destination polygons rather than individual
blocks. That was the substantive finding of PR #330 and it is kept.

- `make_precinct_map()` becomes associate, combine, plot.
- In `extract_precincts.r`:
  - `get_solver_block_destinations()` associates once;
  - `flagged_optimized_distant_blocks()` adds distances and flagging.

One nearest-neighbour implementation and one union implementation exist, composed
differently by each pipeline.

## What this means for the delivered maps

The pipeline produces a different image from the one already delivered, for the same
input data. **A rerun is therefore not a reproduction**, and anyone checking a delivered map
against a fresh run needs to know which behaviour produced which.

The difference is narrow. The delivered data was built on clipped block geometry (from an
old version of `block_precinct_assignment()`), so the drawing conventions change. The larger
change is which outline a block falls inside.

From a population assignment perspective, this difference is immaterial. It only differs on
unassigned blocks. However, the fills on the delivered maps did not match the outlines, and
the delivered maps and the current maps will disagree visually.

### Measured, for Monongalia

Running the old single destination assignment and
the new dissolved-polygon search over the same Monongalia inputs — 2,772 blocks, of which
the solver assigned 2,071 and skipped 701:

- **632 of the 701** empty blocks change `id_dest`, all from "Cheat Lake VFD".

Preliminary checks for run-to-run stability in `R/tests/nearest_destination_determinism.R`
give an appearance of stability. This includes testing for inputs in a different order on
Monongalia data stored locally (no BigQuery) with current libraries. This is not a guarantee
of determinism in the non-populated block assignment.

Potentially affected delivered artifacts, all tracked under
`precinct_analysis_outputs/Monongalia_County_WV/`:
`15_min_optimized_distance_heat_map.png`,
`15_min_total_population_optimized_distance_heat_map.png`,
`20_min_optimized_distance_heat_map.png`, and
`20_min_total_population_optimized_distance_heat_map.png`.

The as-provided precinct maps from Step 6 are untouched — that pipeline never did a spatial
unpopulated block assignment, so it never had this problem.

One column of `optimized_distance_flagged_blocks_*.csv` can also change: `id_dest` for the
unpopulated blocks. Those blocks' distances and
demographics are zero either way, so the fill values the maps draw do not change.


### Reference point for the delivered outputs

If there is any need to recreate the delivered maps, review the commit
**`617353ab`** — "final changes requested by client", 2026-07-24 01:31 UTC. It is the commit
that created the delivered artifacts. The code at that commit is the reference for how they
were produced.

The file layout differs from today's and will not match current paths: `extract_precincts.r`
is at `R/result_analysis/extract_precincts.r` rather than under `scripts/`, the county
config is at `R/result_analysis/Extraction_configs/Monongalia_County_WV.r` rather than
`precinct_configs/`, and only `shape_extraction_functions.r` exists.

Two caveats on precision. The run that produced the artifacts necessarily preceded the
commit that recorded them, and that commit also changed code, so `617353ab` is the closest
available anchor rather than proof of the exact code path. If the old maps need citing
long-term, use the above commit.

Expect agreement on the populated blocks, the drive-time values and the flagged counts.
Expect the 632 zero-population blocks measured above to differ in a run of the current
pipeline, and do not expect the PNGs to be byte-identical — image output depends on
graphics-device and ggplot versions regardless of any of this.

## Consequences

- `extract_precincts.r` no longer depends on `Basic_analysis.r` having been run for the same
  county and config. The two pipelines share functions but no files, no state, and no run
  ordering.
- `Basic_analysis.r` still writes its own precinct shapefile and still associates
  destinations independently, so its standalone precinct map can disagree with Step 7's
  outlines. The divergence moves out of a single image and into two separate outputs. This
  is a known limit, not engineered around; it matters only if the two are compared
  directly.
- The TODO recording that `st_nearest_feature` "seems to assign blocks differently every
  run" is removed. However, the non-determinism question is still open.
- These R scripts have no automated test coverage, so verification is a full rerun of both
  pipelines.