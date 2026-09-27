# Monongalia cleanup plan

How to land the open Monongalia work into `delivery/Monongalia_County`, move the
delivery outputs out of git and into the analyses bucket, and then take the epic
to `dev`.

Checked against `origin` on **2026-09-27**. Re-check before acting if much time
has passed.

**This is a working plan, not documentation.** It lives on the epic so the people
doing the work can find it. The last step before the epic goes to `dev` is to
delete this file.

## The stack

These come from PR base refs, and git agrees: each child contains its parent's
tip. All five are behind the epic by the R cleanup (31–32 commits), which does
not block them — all five are `MERGEABLE`/`CLEAN` against their bases.

```
dev
└── delivery/Monongalia_County            epic · no PR to dev · 130 ahead / 42 behind dev · last commit 2026-09-23
    ├── #330 fix/precinct-nearest-neighbor-drift   clean · 3 commits · assigned Susama
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

**New since 2026-09-21:** the epic is 42 commits behind `dev`, which it was not
before. `dev` has since taken the driving-distance tools (#321) and the Tarrant
2026 work. It needs merging into the epic before the final run, so the run
happens on what will actually reach `dev` — this is step 3 below.

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

2. **The rest into the epic.** #330, #332 and #334 already base the epic, so
   nothing needs retargeting. Merge #332, which now carries the whole storage
   chain, and #330 and #334 in any order.

   #330's only review is a comment from Susama dated 2026-08-02, which predates
   all three of its commits (2026-08-05). It needs a fresh review, not a
   rubber stamp on that comment.

   #334 removes the defensive `| x == ""` guards on the strength of its new
   `safe_fread`, but leaves plain `fread()` at `precinct_shape_functions.r:42`
   and `:782` and `extract_precincts.r:87`. Confirm blanks cannot reach those
   three reads, or convert them too.

3. **Merge `dev` into the epic.** 42 commits behind as of 2026-09-27. Do this
   before the final run, so the run reflects what will reach `dev`.

4. **Final run.** Run `extract_precincts.r` for Monongalia on the epic, with ORS
   up. Every change above affects what this run produces: the R cleanup
   reorganized the scripts, #330 and #334 change what the outputs contain, and
   the storage chain does the uploading. This is the first real upload to the
   bucket.

5. **Verify the bucket.** The run's folder under `precinct-distance-analyses/`
   should hold the outputs, the geojson, `sources/`, and `analysis_manifest.yaml`.
   Do not start step 6 until this is confirmed.

6. **Cleanup PR** (the second part of the #340 follow-up, below):
   - narrow the `.gitignore` rule `!precinct_analysis_outputs/**/*` to the two
     reconciliation files, which hold human decisions rather than plain run
     output: `location_precinct_mismatches.csv` (hand-reviewed each round; its git
     history is the only record of past rounds) and
     `precinct_polling_location_crosswalk.csv` (built from the mismatches by
     `Monongalia_reconciliation.r` and read back by `extract_precincts.r`);
   - `git rm --cached` the other outputs, including the geojson;
   - delete this plan file.

7. **Epic → `dev`.** The cleanup lands first, so the outputs never reach `dev`'s
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
  - *Outputs out of git* (step 6): after a verified upload, narrow the
    `.gitignore` rule to the two reconciliation files and untrack the rest.
- **#335's "tracked separately" items are not tracked anywhere**
  ([note, 2026-09-21](https://github.com/Voting-Rights-Code/Equitable-Polling-Locations/issues/335#issuecomment-5768193087)):
  the long-term home of the reconciliation files, spaces in output filenames, and
  `deprecated/` path modernization. Each needs chasing down. None of them blocks
  this plan; the reconciliation files simply stay tracked where they are.
