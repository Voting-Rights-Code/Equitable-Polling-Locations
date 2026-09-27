# 0003: Build solver precinct outlines from the flagging assignment, not Basic_analysis.r's shapefile

## Status

Accepted

## Context

`extract_precincts.r` Step 7 draws heat maps of the solver's assignment: census blocks
filled by drive time, with precinct-like outlines drawn on top showing which blocks the
solver grouped together. The fill and the outline are separate arguments to
`make_demo_distance_heat_map()`, and they come from separate places. The fill comes from
`solver_distance_flagged_blocks_*`, produced in Step 5 by
`flagged_optimized_distant_blocks()`. The outline is read from a shapefile that
`Basic_analysis.r` wrote earlier, in a different run, via `make_precinct_map()`.

Both sides have to answer the same question, and neither can read it off the solver
output. The solver emits one row per block it assigned, which excludes zero-population
blocks by design. But the maps draw every block in the county. So every block the solver
skipped needs a destination invented for it, purely so it can be coloured and enclosed.

Each side invents it independently. `flagged_optimized_distant_blocks()` ran
`st_nearest_feature` against individual assigned blocks; `make_precinct_map()` ran its own
`st_nearest_feature` against already-dissolved per-destination polygons. Two searches,
different candidate geometry, same question. When they disagreed, a block was filled with
one destination's colour while sitting inside a different destination's outline — visible
drift in a delivered map, with nothing in the data to flag it.

The separation runs deeper than two function bodies. The two sides are in different
scripts, execute in different runs, and derive from different block geometry.
`block_precinct_assignment`, which the flagging path uses, holds geometry from
`st_intersection(county_blocks, county_precincts)` — blocks clipped to their dominant
precinct. `make_precinct_map()` reads full, unclipped TIGER blocks through
`results_with_area_geom()`. The only thing connecting the two is
`get_solver_precinct_shapes()`, which compares file mtimes and stops if the shapefile is
older than the results it should reflect. That guard catches a stale file; it cannot
catch two live computations disagreeing.

There is also a standing doubt about the search itself. A TODO in
`precinct_shape_functions.r` asked whether `st_nearest_feature` is the right tool at all,
"given how the `st_nearest_feature` seems to assign blocks differently every run." If that
is right, the problem is not only that two implementations differ — it is that any single
implementation, called twice, may differ from itself.

## Options considered

1. **Share the fallback as a function.** Extract one helper and have both call sites use
   it. Cheapest, and the shape of the fix attempted in PR #330. It does not close the
   divergence if the underlying search is not deterministic, because two calls can still
   disagree. It also leaves the clipped-versus-unclipped geometry mismatch in place, so
   the two callers are fed different inputs even when they share code.
2. **Have `make_precinct_map()` return its per-block resolved-destination table** and
   have the flagging path merge on it. Shares the result rather than the logic, so it
   survives non-determinism. But the block identifier is destroyed inside
   `make_precinct_map()` before the fallback runs: the populated side is collapsed by
   `summarize()`, and the unpopulated side is then narrowed to those same columns before
   the `st_join`. Delivering this means restructuring the function to carry `id_orig`
   through the dissolve and the join, and it makes a plotting function responsible for
   producing data — which forces `invisible()` wrapping at unrelated call sites in
   `Basic_analysis.r` to stop per-block tables printing to the log.
3. **Infer the assignment by containment against the written shapefile.** The shapefile
   is the exact union of the blocks assigned to each destination — `area_thresh` is
   computed in `make_precinct_map()` but never applied, so nothing is simplified or
   coarsened. A block absorbed into a precinct therefore lies inside that precinct's
   polygon, and containment recovers the map's answer deterministically, with no changes
   to `make_precinct_map()` at all. But it tests clipped block geometry against a union of
   unclipped blocks, so a block trimmed across a boundary can land in the wrong polygon —
   precisely the near-boundary blocks most at risk. It also keeps the cross-script, cross-run
   dependency and inherits the map's fallback rather than owning one.
4. **Build the outline from the flagging assignment and stop reading the shapefile.**
   Dissolve `solver_distance_flagged_blocks_*` against `block_precinct_assignment`
   geometry to produce the outlines.

## Decision

Option 4, together with separating the two operations that were tangled inside
`make_precinct_map()`.

The fill and the outline become two views of one assignment. There is a single
block-to-destination result, the fill is that result joined to distances, and the outline
is that result dissolved. They cannot disagree, because one is derived from the other
rather than computed alongside it. This is a stronger guarantee than either sharing a
function or reconciling two answers after the fact, and it does not depend on the
nearest-neighbour search being deterministic.

Two operations are factored out, in `map_functions.R`, sourced from
`precinct_shape_functions.r`. They are map and geometry operations; the precinct pipeline
is a consumer:

- `dissolve_blocks_by_destination()` — a per-block table plus geometry to one polygon per
  destination. Pure and deterministic. Grouping columns are parameterized, because
  `make_precinct_map()` needs `dest_lat` and `dest_lon` carried through for its points
  layer while the Step 7 outline needs the destination alone.
- `resolve_solver_block_destinations()` — every block to a destination, including the
  fallback for blocks the solver skipped.

Dissolve is the primitive and resolve is layered on top of it, because the better
nearest-neighbour search is against dissolved per-destination polygons rather than
individual blocks. That was the substantive finding of PR #330 and it is kept.
`make_precinct_map()` becomes resolve, dissolve, plot. `flagged_optimized_distant_blocks()`
becomes resolve, then distances and flagging. Step 7's outline is a dissolve of the
already-resolved flagging table. One nearest-neighbour implementation and one union
implementation exist in the codebase, composed differently by each pipeline.

`get_solver_precinct_shapes()`, its mtime guard, and the `SOLVER_PRECINCT_SHAPEFILE`
config entry are removed. That value is read nowhere but `extract_precincts.r`, and there
at lines 98 and 222, which are a redundant double read of the same thing.

## Why delivered output and pipeline output diverge

This change makes the pipeline produce a different image from the one already delivered
for Monongalia County, for the same input data. That is intended, but it means a rerun is
not a reproduction, and anyone checking the delivery against a fresh run needs to know
which behaviour they are looking at.

What differs is the outline only. The fill — which block is which colour, and which blocks
are flagged — is unchanged, because it always came from
`solver_distance_flagged_blocks_*`. What changes is the precinct-like boundary drawn on
top of it, and only on the solver-assignment maps. The as-provided precinct maps from Step
6 are untouched, because nothing in that pipeline ever did a spatial fallback.

Before this change, the outline was drawn from full, unclipped TIGER blocks, so it covered
the holes left by clipping. After it, the outline is dissolved from the same clipped
geometry as the fill, so those holes are cut out of the outline too. The note at the top of
Step 6 records the old behaviour:

> In the optimized maps, the same clipped blocks are used, but the precinct lines are drawn
> the full blocks. Missing block pieces will still appear as holes, but in the same precinct
> as the drawn portion of the block.

A second, smaller difference: any block whose fill and outline previously disagreed — the
defect this decision exists to fix — moves. Those blocks were being drawn inside the wrong
precinct's boundary, and will now be enclosed by the one matching their fill. So some of
the change is the bug being corrected, not a change in convention.

Affected delivered artifacts, all tracked in the repository under
`precinct_analysis_outputs/Monongalia_County_WV/`:
`15_min_optimized_distance_heat_map.png`,
`15_min_population_optimized_distance_heat_map.png`,
`20_min_optimized_distance_heat_map.png`, and
`20_min_population_optimized_distance_heat_map.png`. Their non-`optimized` counterparts are
not affected.

## Which version produces which output

Do not identify the behaviour by date or by branch — this work sits on a delivery epic
whose history includes several merges. Identify it by whether the shapefile read still
exists:

- **Delivered behaviour (outline from full blocks).** Any revision where
  `get_solver_precinct_shapes()` is present in
  `R/result_analysis/utility_functions/precinct_shape_functions.r` and
  `SOLVER_PRECINCT_SHAPEFILE` is defined in the county config. Reproducing a delivered map
  additionally requires running `Basic_analysis.r` for that county and config *first*, so
  the shapefile exists and is newer than the results file; otherwise the mtime guard stops
  the run.
- **Current behaviour (outline from the flagging assignment).** Any revision where those
  two are absent. `extract_precincts.r` can be run on its own.

The delivered PNGs themselves remain in git history regardless, so the artifacts are
recoverable even without rerunning. Prefer retrieving them over attempting a
reproduction.

A fresh run differing from the delivered map in the outline is therefore expected, and is
not a regression. A fresh run differing in the *fill*, or in either
`optimized_distance_flagged_blocks_*.csv`, is not explained by this decision and should be
investigated.

## Consequences

- `extract_precincts.r` no longer depends on `Basic_analysis.r` having been run for the
  same county and config. The two pipelines share functions but no files, no state, and no
  run ordering. This also simplifies the precinct-analysis upload work, since the script no
  longer consumes an artifact produced by another script's run.
- `Basic_analysis.r` still writes its own precinct shapefile and still resolves
  independently, so its standalone precinct map can disagree with Step 7's outlines. The
  divergence moves out of a single image and into two separate outputs. This is a known
  limit, not engineered around; it matters only if the two are compared directly.
- The `st_nearest_feature` non-determinism has to be settled as part of this work, not
  deferred. Reducing it to one call site makes it answerable, but with no test suite the
  only verification available here is a rerun, and a rerun proves nothing while the
  fallback can move between runs. It is a prerequisite for the check below, not a
  follow-up.
- These R scripts have no automated test coverage, so verification is a full rerun of both
  pipelines. From `extract_precincts.r`: the block-to-destination assignments in
  `optimized_distance_flagged_blocks_*.csv` match the Step 7 outlines exactly, with blocks
  near precinct boundaries spot-checked. From `Basic_analysis.r`: the refactored
  `make_precinct_map()` still produces its precinct map and shapefile, since it is rewritten
  here to call resolve and dissolve instead of its own inline versions, and it remains the
  only consumer of its own output.
