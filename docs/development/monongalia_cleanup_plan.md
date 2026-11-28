# Monongalia cleanup plan

What's left before `delivery/Monongalia_County` goes to `dev`. Git and the PRs hold
the history; this file holds only what is still to do and what is still live.

Checked against `origin` on **2026-11-28**. Re-check before acting if time has passed.

**Working plan, not documentation.** The cleanup PR (step 4) deletes it.

## Where things stand

- The epic holds the precinct pipeline and the storage chain (#332, #341, #343, #378).
- It is 3 commits behind `dev`, all docs (#375).
- One PR is open against it: #381, the deliverable folder (draft).
- `feature/376-clean-up-tracking` is left over from #378, which has merged. Delete it.

## Order of work

1. **Land the open work below, in any order.** Everything in "Must land" goes in
   before the epic goes to `dev`.
2. **Final run.** Merge `dev` in, then run
   `extract_precincts.r Monongalia_County_WV.r` on the epic with ORS up. This is the
   first upload to the real bucket. It regenerates the four `*_optimized_*` heat
   maps, where 55 zero-population blocks change destination from what was
   delivered. ADR 0003 records why.
3. **Verify the bucket.** Under
   `precinct-distance-analyses/Monongalia_County_WV_precinct_analysis/distance_analysis/<datestamp>/`:
   every output, the route geojson, and `analysis_manifest.yaml`, with every manifest
   entry matching an object. Do not start step 4 until this is confirmed.
4. **Cleanup PR** (#340, Follow-up 2, second half: outputs out of git):
   - Narrow the `.gitignore` rule `!precinct_analysis_outputs/**/*` to the two
     reconciliation files, which hold human decisions rather than run output:
     `location_precinct_mismatches.csv` (hand-reviewed each round; its git history
     is the only record of past rounds) and `precinct_polling_location_crosswalk.csv`
     (built from the mismatches by `Monongalia_reconciliation.r`, read back by
     `extract_precincts.r`). Their long-term home is #372.
   - `git rm --cached` the other outputs, including the geojson.
   - Delete this file.
5. **Epic → `dev`**, with a merge commit. The cleanup lands first, so the outputs
   never reach `dev`'s tree.

## Must land

| Ticket | What |
|---|---|
| #340, Follow-up 2 | The route geojson joins the main run's upload (before step 2). Then the outputs leave git (step 4). |
| #340, Follow-up 3 | `flag_state_provided_precincts.r` uploads the flagged-precinct layers. The precinct 2A/2B PNG is uploaded once by hand, and its object path is posted on #340. |
| #380 | Part 1: the deliverable folder. Part 2: inputs tracked in git are recorded in the manifest by path and commit, not uploaded. Both in PR #381. |
| #379 | `extract_precincts.r` reads its model inputs from the DB or CSV, and records their `model_run_id`. |
| #377 | Document the precinct analysis workflow. |
| #307 | In the driving-time epic. `results.csv`'s `distance_m` holds seconds for driving-time runs; #307 renames it. Once it lands, `flagged_optimized_distant_blocks()` (`precinct_shape_functions.r`, the `distance_m / 60` TODO) reads the renamed column, and the two `optimized_distance_flagged_blocks_*` CSVs stop labeling seconds as `distance_m`. Before step 2. |

Decided, so not on this list: the optimization run stays required (#340, 2026-11-28).

## Related, not blocking

- #372: where the hand-reviewed reconciliation CSVs live long term.
- #373: output filenames with spaces.
- #374: `deprecated/` and `testing_model_functionality/` scripts cannot run.

## Known issue during the run

**#339.** `pytest` fails
`buffered_extract_test.py::test_buffer_polygon_contains_and_grows_state` with
`Permission denied` on `datasets/openrouteservice/`. This work does not cause it;
do not chase it. `sudo chown -R vscode datasets/openrouteservice` clears it locally.

## Tickets to close by hand

GitHub closes a ticket from a PR only when the PR merges into `main`, so these stay
open although their work is on the epic. Ticket (PR that landed it):

#266 (#278), #267 (#280), #268 (#300), #269 (#292), #270 (#293), #271 (#306),
#272 (#275), #276 (#329), #277 (#300), #282 (#284), #297 (#301), #298 (#301),
#376 (#378).

**Confirm before closing:** #283 (`Monongalia_73` shows zero population). #285 flags
the case, but the winner-take-all block assignment that causes it is unchanged. Close
it only if flagging was the intended fix.
