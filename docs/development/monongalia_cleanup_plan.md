# Monongalia cleanup plan

How to land the open Monongalia work into `delivery/Monongalia_County`, move the
delivery outputs out of git and into the analyses bucket, and then take the epic
to `dev`.

Checked against `origin` on **2026-09-28**. Re-check before acting if much time
has passed.

**This is a working plan, not documentation.** It lives on the epic so the people
doing the work can find it. The last step before the epic goes to `dev` is to
delete this file.

## The stack

These come from PR base refs, and git agrees: each child contains its parent's
tip. The storage chain and #334 are behind the epic by the R cleanup and the `dev`
merge (75–76 commits), which does not block them — a local test merge of each onto
the epic tip is conflict-free. #368 is behind only by the epic's own edits to
this plan.

```
dev
└── delivery/Monongalia_County            epic · no PR to dev · 137 ahead / 0 behind dev · last commit 2026-09-28
    ├── #368 fix/333-share-block-destination-resolution  mergeable · 13 commits · assigned Daniel · ticket #333
    ├── #334 fix/na-blank-normalization            clean · 1 commit · assigned Susama
    └── #332 feature/generalize_storage.R          clean · 1 commit · assigned Chad · ticket: none
        └── #341 fix/335-manifest-tree-relative    clean · 1 commit · ticket #335
            └── #343 feature/340-precinct-snapshot-upload  clean · 1 commit · ticket #340
```

The storage chain (#332, #341, #343) is one feature split three ways. #332
generalizes `storage.R` but introduced defects, listed on #335. #341 fixes those
defects by merging *into* #332's branch. #343 then adds the precinct snapshot
upload, which is the first half of #340. So **#332 is not ready to merge on its
own**; it goes last in its chain, carrying all three.

**`dev` is merged in** as of `c0f61da2` (2026-09-27), bringing the
driving-distance tools (#321) and the Tarrant 2026 work, so the final run will
happen on what actually reaches `dev`. Two conflicts came with it, both resolved:
`python/tests/ors_up_cli_test.py` took `dev`'s version wholesale, and
`python/CLAUDE.md` took the union. Re-merge `dev` if much time passes before the
final run.

## Order of work

Standard operating procedure, for every merge in this plan:

- Merge with a **merge commit, not a squash**. This repo has no default merge
  strategy, and a squash here would make the next PR in the stack replay commits
  that already landed.
- **Delete the branch immediately.** Any PR pointing at it is then retargeted to
  where it merged.

The automatic retarget fires only when the deleted branch has a merged PR of its
own that covers its current tip. Deleting immediately is what keeps that true.

**If you forget to delete immediately** and more work lands on that branch, the
condition no longer holds, and deleting it later can close the PRs based on it
instead of retargeting them. Retarget the dependents explicitly first:

```bash
# before deleting <branch>
gh pr list --state open --json number,headRefName,baseRefName \
  --jq '.[]|select(.baseRefName=="<branch>")'
# for each result
gh pr edit <n> --base <where the branch merged>
```

**Example.** On 2026-09-27 `feature/optimization_output_maps` was deleted and
#330, #332 and #334 **closed unmerged** rather than retargeting; recovering them
took a branch restore, a reopen, and a manual retarget of each.

1. **Storage chain, into `feature/generalize_storage.R`.** Independent of the
   rest, so it can start now.
   - Merge #341 and delete `fix/335-manifest-tree-relative` immediately; #343
     retargets to `feature/generalize_storage.R`.
   - Merge #343.
   - The geojson follow-up (below), as a new PR under #340.

2. **The rest into the epic.** #332, #334 and #368 already base the epic, so
   nothing needs retargeting. Merge #332, which now carries the whole storage
   chain, then #334, and #368 before the final run (below).

   **#330 is closed, not merged.** It shared the empty-block fallback as a
   *function*; that cannot close the divergence if `st_nearest_feature` assigns
   differently between runs, so the fallback has to be computed once and shared as
   data. The replacement is #368, built to the revised plan on
   [#333](https://github.com/Voting-Rights-Code/Equitable-Polling-Locations/issues/333#issuecomment-5860131935).
   All seven steps of that plan are done, including the regression check of both
   pipelines; results are on #333.

   **#368 has to land before the final run.** Besides #333's work, it repairs merge
   `b6104a0b`, which left `make_demo_distance_heat_map()` with a signature its
   callers do not match. On the epic as it stands, `extract_precincts.r` stops at
   Step 6.

   How #330 got into the state it did is recorded in a
   [timeline comment](https://github.com/Voting-Rights-Code/Equitable-Polling-Locations/pull/330#issuecomment-5857142852)
   on the PR — read that rather than reconstructing it, which took an afternoon.
   The short version: its only review was submitted against `52b48124`, a commit
   force-pushed out of the branch, so nothing in the PR was ever reviewed; its
   summary accurately describes that vanished commit; and it could not run, because
   `merge(all_blocks, results, ...)` collides on `population` and the closing
   `results_full[, ..output_columns]` raises `column not found: [population]`.

   #368 changes a delivered output, the solver-assignment heat maps: on Monongalia,
   55 zero-population blocks change destination, and nothing else moves. ADR 0003
   records why and which artifacts. The final run regenerates those maps.

   #334 removes the defensive `| x == ""` guards on the strength of its new
   `safe_fread`, but leaves plain `fread()` at `precinct_shape_functions.r:42`
   and `:782` and `extract_precincts.r:87`. Confirm blanks cannot reach those
   three reads, or convert them too. The first two are the same function,
   `get_polling_locations()`, defined twice by merge `b6104a0b`; #368 removes the
   duplicate, leaving one to convert.

3. **Final run.** Run `extract_precincts.r` for Monongalia on the epic, with ORS
   up. Every change above affects what this run produces: the R cleanup
   reorganized the scripts, #334 changes what the outputs contain, and the storage
   chain does the uploading. This is the first real upload to the bucket. With
   #368 in, this run also regenerates the solver-assignment heat maps with outlines
   built from the flagging assignment — see ADR 0003.

4. **Verify the bucket.** The run's folder under `precinct-distance-analyses/`
   should hold the outputs, the geojson, `sources/`, and `analysis_manifest.yaml`.
   Do not start step 5 until this is confirmed.

5. **Cleanup PR** (the second part of the #340 follow-up, below):
   - narrow the `.gitignore` rule `!precinct_analysis_outputs/**/*` to the two
     reconciliation files, which hold human decisions rather than plain run
     output: `location_precinct_mismatches.csv` (hand-reviewed each round; its git
     history is the only record of past rounds) and
     `precinct_polling_location_crosswalk.csv` (built from the mismatches by
     `Monongalia_reconciliation.r` and read back by `extract_precincts.r`);
   - `git rm --cached` the other outputs, including the geojson;
   - delete this plan file.

6. **Epic → `dev`.** The cleanup lands first, so the outputs never reach `dev`'s
   tree.

Why this order:

- **Parent before child keeps each PR's merged diff equal to its reviewed diff.**
  Merging a child first lands it *inside the parent's branch*, so the parent's PR
  silently grows after it was reviewed. The underlying rule is "don't change a PR's
  content after it has been reviewed."
- **The exception is a fix for its parent.** #341 exists to fix #332, so it lands
  in #332's branch before #332 merges, and #332 is reviewed with the fix in it.
- **Merge commits make this safe.** After a parent merges, a retargeted child
  still shows only its own commits.

## Tickets

- **#340 holds both halves of the outputs work**, as a follow-up after #343
  ([comment, 2026-09-21](https://github.com/Voting-Rights-Code/Equitable-Polling-Locations/issues/340#issuecomment-5768195389)).
  Chad has been asked whether he'd rather split it into its own ticket.
  - *Geojson into the upload* (step 1): `extract_precincts.r` runs the route fetch
    after writing the 20-minute CSV, behind a per-county config switch because it
    needs ORS, and registers the geojson so it uploads with everything else.
  - *Outputs out of git* (step 5): after a verified upload, narrow the
    `.gitignore` rule to the two reconciliation files and untrack the rest.
- **#333 replaces #330**, is assigned to Susama, and has a
  [revised plan](https://github.com/Voting-Rights-Code/Equitable-Polling-Locations/issues/333#issuecomment-5860131935)
  that supersedes the ticket body. It factors the empty-block fallback into
  `associate_destinations_to_all_blocks()` and `combine_blocks_by_destination()`,
  and builds Step 7's outline from the flagging assignment instead of reading
  `Basic_analysis.r`'s shapefile — so fill and outline become two views of one
  result and cannot disagree. `get_solver_precinct_shapes()` and
  `SOLVER_PRECINCT_SHAPEFILE` go away with it.

  Its two "already landed" items are on this epic via 276 (`6b0e5b3f`): geometry
  standardized on TIGER's native NAD83 (`TIGER_CRS`), and a real "all blocks
  accounted for" check in `compute_block_precinct_overlaps()`. All seven steps of
  the revised plan are done, and are in PR #368, assigned to Daniel.

  Two consequences for this plan. **This changes a delivered output** — the four
  `*_optimized_*` heat maps under `precinct_analysis_outputs/Monongalia_County_WV/`,
  where 55 zero-population blocks change destination. ADR 0003 records why, which
  artifacts, and how to tell which behaviour a revision produces. And #368 also
  carries the repair without which the final run cannot get past Step 6 (step 2
  above), so it lands before step 3. Its regression check was run locally, without
  uploading the precinct outputs, and does not replace the final run.
  One follow-up stays open on #333: the 20-minute maps' fill comes from its own
  association, separate from the outline's. The two agree today.
- **#339 — `buffered_extract` test failure is expected, and is not ours.**
  `pytest` fails one unit test on this epic:
  `buffered_extract_test.py::test_buffer_polygon_contains_and_grows_state`,
  with `Permission denied` writing
  `datasets/openrouteservice/georgia-buffer.geojson`. Nothing in the Monongalia
  work causes it, and nothing here fixes it — the three files involved are
  byte-identical to `dev`.

  The test patches `buffered_extract.ORS_DATA_DIR`, but the output path comes
  from `buffer_polygon_path()`, which reads `ors_setup.ORS_DATA_DIR` — a
  separate binding the patch never touches. So the write escapes `tmp_path` and
  lands in the real directory. On a writable checkout it passes silently and
  just rewrites that file with byte-identical content and a fresh mtime, which
  is how it went unnoticed; where the directory is root-owned (an ORS container
  created it that way), the same bug fails hard instead.

  Do not chase it during the final run, and do not confuse it with the separate
  `dev` pytest failures Chad traced to the test database being ahead of `dev`'s
  migrations. Chad's fix is folded into #338, not a standalone PR.
  `sudo chown -R vscode datasets/openrouteservice` clears the local symptom.
- **#335's "tracked separately" items are not tracked anywhere**
  ([note, 2026-09-21](https://github.com/Voting-Rights-Code/Equitable-Polling-Locations/issues/335#issuecomment-5768193087)):
  the long-term home of the reconciliation files, spaces in output filenames, and
  `deprecated/` path modernization. Each needs chasing down. None of them blocks
  this plan; the reconciliation files simply stay tracked where they are.
