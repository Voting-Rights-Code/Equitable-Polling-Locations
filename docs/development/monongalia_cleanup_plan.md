# Monongalia cleanup plan

How to land the open Monongalia work into `delivery/Monongalia_County`, move the
delivery outputs out of git and into the analyses bucket, and then take the epic
to `dev`.

Checked against `origin` on **2026-09-21**. Re-check before acting if much time
has passed.

**This is a working plan, not documentation.** It lives on the epic so the people
doing the work can find it. The last step before the epic goes to `dev` is to
delete this file.

## The stack

These come from PR base refs, and git agrees: each child contains its parent's
tip, except `generalize_storage.R`, which is one commit behind 276 (harmless).

```
dev
└── delivery/Monongalia_County            epic · no PR to dev · 175 ahead / 0 behind dev · last commit 2026-09-21
    └── feature/optimization_output_maps  already merged into the epic (#312, 2026-07-29)
        └── #329 feature/276-R-clean-up   CONFLICTING · 18 commits · assigned Daniel · no reviews
            ├── #330 fix/precinct-nearest-neighbor-drift   clean · 3 commits · assigned Susama (commented)
            │        port-pr330-cleanup is an identical copy (0 commits different either way)
            ├── #334 fix/na-blank-normalization            clean · 1 commit · assigned Susama
            └── #332 feature/generalize_storage.R          clean · 1 commit · assigned Chad · ticket: none
                └── #341 fix/335-manifest-tree-relative    clean · 1 commit · ticket #335
                    └── #343 feature/340-precinct-snapshot-upload  clean · 1 commit · ticket #340
```

The problem is at the root. #329's base, `feature/optimization_output_maps`, was
already merged into the epic before #329 was opened, so the whole stack is built
on a branch whose work went in by another route.

The storage chain (#332, #341, #343) is one feature split three ways. #332
generalizes `storage.R` but introduced defects, listed on #335. #341 fixes those
defects by merging *into* #332's branch. #343 then adds the precinct snapshot
upload, which is the first half of #340. So **#332 is not ready to merge on its
own**; it goes last in its chain, carrying all three.

## How big #329 really is

GitHub shows +12,478 / −1,078 across 61 files. Most of that is one file:

- **+11,565** is `precinct_analysis_outputs/Monongalia_County_WV/long_drive_time_routes.geojson`
  and **+152** is `python/scripts/delivery_scripts/fetch_long_drive_time_routes.py`.
  Both are **byte-identical** to what the epic already has (from #326, merged
  into the epic by `9242535f` on 2026-09-08), so they add nothing when #329 lands.
- **R code is +734 / −1,050 across 21 files**, a net deletion.
- By change type: 22 modified, 22 deleted (seven `scratch_*.r` files and the
  `_old/` and `_v2/` output folders), 10 moved *and* edited, 3 moved unchanged,
  4 added.

So it is mostly a reorg, but not only one: ten files were rewritten as they moved.

Retargeting #329 will **not** shrink GitHub's number. The number drops once the
epic is merged into 276.

## What the conflict is

An in-memory merge of 276 into the epic conflicts in 15 files.

**Two R files, 13 hunks:** `scripts/extract_precincts.r` (7) and
`utility_functions/precinct_shape_functions.r` (6). One side moved the files and
the other edited them in place:

- 276 moved and rewrote both files: `R/result_analysis/extract_precincts.r` →
  `R/result_analysis/scripts/extract_precincts.r` (53% of lines kept), and
  `utility_functions/shape_extraction_functions.r` →
  `utility_functions/precinct_shape_functions.r` (57% kept).
- The epic kept the old paths and received #323's edits there (+103 / −13) via
  `9242535f`. Git follows the move and tries to replay #323 onto the rewritten
  files.

**276 already has #323**, so these conflicts are bookkeeping, not lost work.
Checked function by function, not by path:

- `get_polling_locations` and `force_text_for_spreadsheet` are identical.
- `get_solver_precinct_shapes` has the same logic; 276 adds comments and
  renumbers "Step 5" to "Step 7" as part of the reorg.
- The polling-location points, the `tableau_theme.R` source, and the
  spreadsheet-safe CSV copies are all present in 276.

**One piece of #323 is missing from 276:** a 9-line comment in
`extract_precincts.r`, just before the heat maps, explaining that blocks are
clipped to precincts by dominant area, so missing block pieces appear as holes.
Re-add it when resolving.

**One file moved on one side and deleted on the other:**
`R/result_analysis/utility_functions/Tarrant_County_TX_exploration.r`. 276 moves
it to `deprecated/`; `dev` deleted it (`5623c855`, 2026-08-29, in the Tarrant 2026
delivery work, which replaced it with `Tarrant_County_TX_closure_analysis.r`).
This conflict arrived with the epic's 2026-09-21 merge of `dev`. Accept the
deletion.

**Twelve generated outputs** in `precinct_analysis_outputs/Monongalia_County_WV/`
(8 heat-map PNGs, 4 flagged-block CSVs). Both sides regenerated them. Do not
hand-merge these: take either side. They are regenerated for real in the final
run (step 5).

**Resolution:** take 276's side for both R files, re-add the holes comment,
accept the Tarrant deletion, and take either side of the outputs.

## Order of work

Every merge uses a **merge commit, not a squash**. This repo has no default merge
strategy, and a squash here would make the next PR in the stack replay commits
that already landed.

1. **Prep.**
   - Retarget #329 from `feature/optimization_output_maps` to
     `delivery/Monongalia_County`, *before* anyone deletes
     `feature/optimization_output_maps`. Deleting the base branch of an open PR
     can close that PR.
   - Delete `port-pr330-cleanup`. It is an exact copy of #330's branch.

2. **Storage chain, into `feature/generalize_storage.R`.** Independent of #329,
   so it can start now.
   - Merge #341. GitHub then retargets #343 onto `feature/generalize_storage.R`.
   - Merge #343.
   - The geojson follow-up (below), as a new PR under #340.

3. **#329 into the epic.** Merge the epic into 276 and resolve as above, so the
   review sees the real merged state. Then Daniel reviews and it merges. This is
   the bottleneck.

4. **The rest into the epic.** When 276's branch is deleted, GitHub retargets
   #330, #332 and #334 to the epic. Merge #332, which now carries the whole
   storage chain, and #330 and #334 in any order.

5. **Final run.** Run `extract_precincts.r` for Monongalia on the epic, with ORS
   up. Every change above affects what this run produces: 276 reorganizes the
   scripts, #330 and #334 change what the outputs contain, and the storage chain
   does the uploading. This is the first real upload to the bucket.

6. **Verify the bucket.** The run's folder under `precinct-distance-analyses/`
   should hold the outputs, the geojson, `sources/`, and `analysis_manifest.yaml`.
   Do not start step 7 until this is confirmed.

7. **Cleanup PR** (the second part of the #340 follow-up, below):
   - narrow the `.gitignore` rule `!precinct_analysis_outputs/**/*` to the two
     reconciliation files, which hold human decisions rather than plain run
     output: `location_precinct_mismatches.csv` (hand-reviewed each round; its git
     history is the only record of past rounds) and
     `precinct_polling_location_crosswalk.csv` (built from the mismatches by
     `Monongalia_reconciliation.r` and read back by `extract_precincts.r`);
   - `git rm --cached` the other outputs, including the geojson;
   - delete this plan file.

8. **Epic → `dev`.** The cleanup lands first, so the outputs never reach `dev`'s
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
  - *Geojson into the upload* (step 2): `extract_precincts.r` runs the route fetch
    after writing the 20-minute CSV, behind a per-county config switch because it
    needs ORS, and registers the geojson so it uploads with everything else.
  - *Outputs out of git* (step 7): after a verified upload, narrow the
    `.gitignore` rule to the two reconciliation files and untrack the rest.
- **#335's "tracked separately" items are not tracked anywhere**
  ([note, 2026-09-21](https://github.com/Voting-Rights-Code/Equitable-Polling-Locations/issues/335#issuecomment-5768193087)):
  the long-term home of the reconciliation files, spaces in output filenames, and
  `deprecated/` path modernization. Each needs chasing down. None of them blocks
  this plan; the reconciliation files simply stay tracked where they are.
