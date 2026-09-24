# 0002: Route on a state-plus-50 km buffered extract, not a single-state extract

## Status

Accepted

## Context

The driving-distance tools route every census block centroid to every potential polling
location through a local OpenRouteService (ORS) instance. ORS routes only on the roads in
the map it is given.

The first version of the tools built that map from a single-state Geofabrik extract. A
Geofabrik state extract is cut along the state line. Roads that cross the line are kept
up to the crossing and then stop. Interchanges, cross-streets, and return loops on the
far side are missing.

This produces a silent error. When the fastest drive between two points inside the state
dips briefly across the state line, ORS cannot see that path. It returns the best route
on the map it has: a longer route that stays inside the state. The result is a normal
distance in meters, HTTP 200, no flag. A true no-route returns null; a border detour does
not.

The error is not random noise. Every block near the affected stretch of border is
inflated in the same direction. The Kolm-Pollak objective penalizes inequality of
access, so a cluster of inflated distances tells the optimizer that one community has
worse access than it does. For an equity tool, a coherent geographic bias is the worst
kind, and it is invisible in aggregate statistics.

Exposure depends on the county. An interior county such as Gwinnett, GA sees none of it.
A county on a state line can see a material amount, concentrated in its border blocks.
A test pair near Morgantown, WV shows the effect: about 15 minutes through Pennsylvania,
or over half an hour along the river and through Morgantown on a West Virginia-only map.

## Options considered

1. **Single-state extract, document the limitation.** Lowest cost. Leaves the silent bias
   in place for every border county.
2. **State plus all neighboring states, merged into one graph.** No heuristic and no
   false negatives. Pays a much larger graph build and more RAM for every county, and
   needs a table of which states neighbor which. Texas with its neighbors, or a state
   that borders eight others, may not fit in the RAM available.
3. **Buffered strip: the state polygon grown by a fixed margin, clipped from a larger
   source.** No heuristic and no false negatives for any route that stays within the
   margin. The graph grows by a predictable, modest amount. Needs a clipping tool and a
   boundary polygon per state.
4. **Two passes: single state first, then a bigger graph for flagged pairs, take the
   minimum.** Pays the big build only for border counties. Needs a flagging heuristic,
   two graphs, and a merge step, and carries a false-negative risk if the heuristic
   misses a pair.

Two approaches were rejected outright. A public routing API as a fallback for border
pairs reintroduces rate limits and per-request cost, and makes results depend on a map
that changes over time. ORS routing profiles that penalize border crossings solve the
opposite problem: they cannot route on roads that are not in the graph.

## Decision

Option 3, a buffered strip with a 50 km margin, clipped from a cached full-US OSM file.

Why 50 km: the tool measures drives from a home to a polling place, which are short. A
route that needs to leave the state by more than 50 km to save time is an hour-plus
trip that no analysis would count as reasonable access. So 50 km catches every shortcut
that matters at little cost. The margin is one constant, easy to change.

Why the full-US file as the clipping source: one source covers every state, handles
corners where three or four states meet, and requires no human to pick neighbors. The
cost is a one-time download of about 12 GB and disk space for one buffered file per
state.

Why a bundled boundary file: the state outlines are committed to the repository, so the
buffer is the same for everyone, with no runtime download and no API key. Because the
margin is 50 km, the precision of the outline does not matter.

The extract step is automatic. The driving-distance orchestrator builds the buffered
file before it starts ORS and skips the step when the file exists. Nothing changes in the
command a user types.

The detour-ratio diagnostic, which compares driving distance to straight-line distance
per pair, was built alongside this decision. It measures the exposure for a county and
shows the effect of the buffer before and after.

## Consequences

- Border detours within 50 km of the state line no longer inflate distances. The
  acceptance test routes the Morgantown pair on a West Virginia buffered graph and
  asserts the route crosses north of the Pennsylvania line, which a single-state graph
  cannot do.
- Every state pays for the buffer, including interior counties that do not need it. The
  graph is larger and takes longer to build. Large states with many neighbors need more
  memory for ORS; Texas needs a 16 GB Java heap.
- A one-time download of the full-US file, about 12 GB, and one buffered file per state
  on disk. Delete the full-US file to refresh it.
- A route that would cross a neighboring state and enter a third state is still
  truncated. For drives within a county this does not happen in practice. It is a known
  limit, not engineered around.
