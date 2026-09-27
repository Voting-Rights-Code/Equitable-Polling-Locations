# 0003: Solver precinct outlines differ from what was delivered — now built entirely within the precinct_analysis pipeline, not from Basic_analysis.r's outputs

## Status

Accepted

## Context

### How the delivered maps were built

The solver-assignment heat maps delivered for Monongalia County were not produced by one
script in one run. They were assembled from two scripts, run in sequence, each supplying
half of the image.

First `Basic_analysis.r` was run for the county and config. Among its outputs,
`make_precinct_map()` wrote `<location>_precinct_<descriptor>.shp` — the dissolved,
precinct-like polygons showing which blocks the solver grouped together — into that
config's `result_analysis_outputs/` folder.

Then `extract_precincts.r` was run. It computed its own block-level data in Step 5, and in
Step 7 it read that shapefile back through `get_solver_precinct_shapes()`, pointed at it by
the `SOLVER_PRECINCT_SHAPEFILE` entry in the county config. `make_demo_distance_heat_map()`
takes the fill data and the outline geometry as separate arguments, so the delivered image
combined:

- **fill** — `solver_distance_flagged_blocks_*`, computed in this run of
  `extract_precincts.r` by `flagged_optimized_distant_blocks()`;
- **outline** — a shapefile written by a *previous* run of a *different* script.

The only thing tying the halves together was a staleness check inside
`get_solver_precinct_shapes()`: it compares the shapefile's mtime against the results
file's and stops if the shapefile is older. The county config carried a matching warning to
"rerun that script for this county/config if `OPTIMIZATION_RESULTS` changes, to keep this
in sync."

### Why that was a problem

The two halves never described the same blocks, and could not, because each derived its
geometry from a different source.

`extract_precincts.r` works from `block_precinct_assignment`, whose geometry comes from
`st_intersection(county_blocks, county_precincts)` — every block **clipped** to its dominant
precinct. `make_precinct_map()` works from `results_with_area_geom()`, which reads **full,
unclipped** TIGER blocks. So the fill described clipped blocks while the outline was drawn
around full ones. The note at the top of Step 6 records this as understood behaviour:

> In the optimized maps, the same clipped blocks are used, but the precinct lines are drawn
> the full blocks. Missing block pieces will still appear as holes, but in the same precinct
> as the drawn portion of the block.

On top of that, each half had to invent data the solver never produced. The solver emits one
row per block it assigned, which excludes zero-population blocks by design, but the maps
draw every block in the county. So every skipped block needed a destination invented for it
purely so it could be coloured and enclosed — and each half invented it separately.
`flagged_optimized_distant_blocks()` ran `st_nearest_feature` against individual assigned
blocks; `make_precinct_map()` ran its own `st_nearest_feature` against already-dissolved
per-destination polygons. Two searches, different candidate geometry, same question.

When those two searches disagreed, a block was filled with one destination's colour while
sitting inside a different destination's outline. That is a wrong answer in a delivered map,
and nothing in the data flags it: both halves are internally consistent, the mtime guard
passes, and the disagreement is visible only by looking at the picture. The staleness check
catches an out-of-date file; it cannot catch two live computations differing.

### Why the previous arrangement could not be patched

Three attempts were considered against the delivered structure, and each failed on
something about that structure rather than on effort.

Sharing the fallback as a common function — the shape of PR #330 — does not work, because a
TODO in `precinct_shape_functions.r` recorded that `st_nearest_feature` "seems to assign
blocks differently every run." If that holds, one shared function called twice can disagree
with itself, so sharing code is not sufficient at any level of care. It also leaves the
clipped-versus-unclipped mismatch untouched: the two callers are fed different geometry even
when they run identical code.

Having `make_precinct_map()` hand its per-block assignment to the flagging path is blocked
by the function's own internals. The block identifier is destroyed before the fallback runs:
the populated blocks are collapsed by `summarize()`, and the unpopulated side is then
narrowed to those same columns before the `st_join`. There is no per-block table at that
point to hand over, and producing one means restructuring the function and making a plotting
routine responsible for returning data.

Reconciling after the fact — having the flagging path infer assignments by containment
against the written shapefile — is closer, and cheap, since `make_precinct_map()` computes
an `area_thresh` but never applies it, so the shapefile is the exact union of its blocks.
But it still tests clipped geometry against a union of unclipped blocks, so a block trimmed
across a boundary can land in the wrong polygon — exactly the blocks at risk. And it keeps
the cross-script, cross-run dependency that made the problem possible.

The common thread is that the delivered arrangement is not one pipeline with a bug in it.
It is two pipelines, each deriving its own geometry and inventing its own answers, joined by
a file and a timestamp.

## Decision

`extract_precincts.r` produces the solver precinct outline itself, from its own data, and
stops reading anything `Basic_analysis.r` wrote.

The outline is built by dissolving `solver_distance_flagged_blocks_*` against
`block_precinct_assignment` geometry. The fill is that same table joined to distances. Fill
and outline become two views of one assignment, derived one from the other rather than
computed alongside each other, so they cannot disagree — a stronger guarantee than sharing
code or reconciling answers, and one that does not depend on the nearest-neighbour search
being deterministic.

`get_solver_precinct_shapes()`, its mtime guard, and the `SOLVER_PRECINCT_SHAPEFILE` config
entry are removed. That value is read nowhere but `extract_precincts.r`, and there at lines
98 and 222, which are a redundant double read of the same thing. `Basic_analysis.r` keeps
writing its own shapefile for its own precinct map; nothing else consumes it.

To avoid replacing one duplicated computation with another, the two operations tangled
inside `make_precinct_map()` are factored out into `map_functions.R`, sourced from
`precinct_shape_functions.r` — they are map and geometry operations, and the precinct
pipeline is a consumer:

- `dissolve_blocks_by_destination()` — a per-block table plus geometry to one polygon per
  destination. Pure and deterministic. Grouping columns are parameterized, because
  `make_precinct_map()` needs `dest_lat` and `dest_lon` carried through for its points layer
  while the outline needs the destination alone.
- `resolve_solver_block_destinations()` — every block to a destination, including the
  fallback for blocks the solver skipped.

Dissolve is the primitive and resolve is layered on it, because the better nearest-neighbour
search is against dissolved per-destination polygons rather than individual blocks. That was
the substantive finding of PR #330 and it is kept. `make_precinct_map()` becomes resolve,
dissolve, plot. `flagged_optimized_distant_blocks()` becomes resolve, then distances and
flagging. Step 7's outline is a dissolve of the already-resolved flagging table. One
nearest-neighbour implementation and one union implementation exist, composed differently by
each pipeline.

## What this means for the delivered maps

The pipeline now produces a different image from the one already delivered, for the same
input data. **A rerun is therefore not a reproduction**, and anyone checking a delivered map
against a fresh run needs to know which behaviour produced which.

Two things differ, and they differ for different reasons.

**The outline convention changed.** It is now dissolved from the same clipped geometry as
the fill, where it was previously drawn from full blocks. Holes left by clipping were
covered by the old outline; they are now cut out of it. This is a deliberate change of
convention, and it is the price of having outline and fill describe the same thing.

**Some blocks were simply wrong before.** Any block whose fill and outline disagreed — the
defect this decision exists to fix — was being drawn inside the wrong precinct's boundary.
Those blocks move, and that part of the difference is a correction, not a convention change.
The two are not separable by inspection, which is why the whole difference has to be treated
as expected rather than audited map-by-map.

Affected delivered artifacts, all tracked under
`precinct_analysis_outputs/Monongalia_County_WV/`:
`15_min_optimized_distance_heat_map.png`,
`15_min_population_optimized_distance_heat_map.png`,
`20_min_optimized_distance_heat_map.png`, and
`20_min_population_optimized_distance_heat_map.png`.

Nothing else changes. The fill values, the flagged CSVs, and the as-provided precinct maps
from Step 6 are all untouched — Step 6's pipeline never did a spatial fallback, so it never
had this problem. A fresh run differing from a delivered map **in the outline** is expected.
A fresh run differing in the **fill**, or in `optimized_distance_flagged_blocks_*.csv`, is
not explained by this decision and should be investigated.

## Which version produces which output

Do not identify the behaviour by date or by branch — this work sits on a delivery epic whose
history includes several merges, and the delivered artifacts were committed across a range
of dates. Identify it by whether the cross-script read still exists:

- **Delivered behaviour, outline from `Basic_analysis.r`'s shapefile.** Any revision where
  `get_solver_precinct_shapes()` is present in
  `R/result_analysis/utility_functions/precinct_shape_functions.r` and
  `SOLVER_PRECINCT_SHAPEFILE` is defined in the county config. Reproducing a delivered map
  also requires running `Basic_analysis.r` for that county and config **first**, so the
  shapefile exists and is newer than the results file; otherwise the mtime guard stops the
  run.
- **Current behaviour, outline from the flagging assignment.** Any revision where those two
  are absent. `extract_precincts.r` runs on its own.

### Reference point for the delivered outputs

**`8f4096cc`** — "more refactoring. state-county mismatch logging changed.", 2026-07-31
05:45 UTC. It is the last commit to write both the four `*_optimized_*` PNGs and
`optimized_distance_flagged_blocks_*.csv`, so the artifacts committed there are the
delivered outputs, and the code at that commit is the reference for how they were produced.
`get_solver_precinct_shapes()` and `SOLVER_PRECINCT_SHAPEFILE` are both present at it, which
confirms the old, shapefile-reading behaviour.

The file layout differs from today's and will not match current paths: `extract_precincts.r`
is at `R/result_analysis/extract_precincts.r` rather than under `scripts/`, the county
config is at `R/result_analysis/Extraction_configs/Monongalia_County_WV.r` rather than
`precinct_configs/`, and both `shape_extraction_functions.r` and
`precinct_shape_functions.r` exist, since 276's rename was mid-flight.

Two caveats on precision. The run that produced the artifacts necessarily preceded the
commit that recorded them, and that commit also changed code, so `8f4096cc` is the closest
available anchor rather than proof of the exact code path. And it is an ancestor of
`delivery/Monongalia_County` but not yet of `main`; it will reach `main` through the epic's
merge, but if this needs citing long-term, tag it rather than relying on branch
reachability. The SHA recorded here is the durable reference either way.

### Rerunning will not reproduce byte-identical output, even at that commit

This is a property of the old code, not of the change. The empty-block fallback uses
`st_nearest_feature`, and the TODO quoted above records that it "seems to assign blocks
differently every run." Any block the solver skipped can therefore be attributed to a
different destination on a second run of the same code against the same inputs, which moves
both the fill colour of that block and the outline it falls inside.

So for verification purposes, treat the committed artifacts as the authoritative record of
what was delivered, and treat `8f4096cc` as the reference for inspecting and running the
code that produced them. Expect agreement on the populated blocks, the drive-time values,
and the flagged counts — the parts that do not depend on the fallback. Do not expect byte
equality on the PNGs or exact agreement on the destination assigned to a zero-population
block.

Settling that non-determinism is part of the current work (see Consequences), which will
make future outputs reproducible in a way the delivered ones are not.

## Consequences

- `extract_precincts.r` no longer depends on `Basic_analysis.r` having been run for the same
  county and config. The two pipelines share functions but no files, no state, and no run
  ordering. This also simplifies the precinct-analysis upload work, since the script no
  longer consumes an artifact produced by another script's run.
- `Basic_analysis.r` still writes its own precinct shapefile and still resolves
  independently, so its standalone precinct map can disagree with Step 7's outlines. The
  divergence moves out of a single image and into two separate outputs. This is a known
  limit, not engineered around; it matters only if the two are compared directly.
- The `st_nearest_feature` non-determinism has to be settled as part of this work, not
  deferred. Reducing it to one call site makes it answerable, but with no test suite the only
  verification available is a rerun, and a rerun proves nothing while the fallback can move
  between runs.
- These R scripts have no automated test coverage, so verification is a full rerun of both
  pipelines. From `extract_precincts.r`: the block-to-destination assignments in
  `optimized_distance_flagged_blocks_*.csv` match the Step 7 outlines exactly, with blocks
  near precinct boundaries spot-checked. From `Basic_analysis.r`: the refactored
  `make_precinct_map()` still produces its precinct map and shapefile, since it is rewritten
  here to call resolve and dissolve instead of its own inline versions.
