# Branch audit

A working record of every branch on `origin`: what happened to its work, and
whether to keep or delete it. It lives on `chore/branch-audit` and is not meant
for `main`.

Current as of **2026-09-21**, checked against `origin` after `git fetch --prune`
and against GitHub's open PR list.

## How we work on this

**`branch_audit.csv` is the only data file.** One file, one row per branch. No
sibling CSVs, no `_v2`.

Turn-taking, because a spreadsheet lock and a script cannot both hold the file:

1. SA edits in LibreOffice, then **saves and closes**.
2. SA says go.
3. Claude reads the file, edits it, and writes back to **the same path**, never
   to a new file.

Every change shows up as a git diff, so it can be reviewed or reverted.

Rules:

- **Do not add columns.** If something needs explaining, it goes in this README.
- **Do not guess into a cell.** Blank means unknown. A wrong value is worse than
  an empty one, because it looks like it was checked.
- Claude records the evidence behind any value it fills in, here in this README.
- Claude documents only. Branch deletions are done by SA.
- Changes to the CSV make parts of this README stale: the totals under "The
  CSV", every list under "Where things stand", and the "Current as of" date.
  Update them in the same change.

`branch_audit.ods` is SA's local spreadsheet. Claude does not write to it, and
it is not tracked.

## The CSV

| Column | Meaning |
|---|---|
| `Branch Name` | One row per branch on `origin`. The CSV mirrors the remote: when a branch is deleted, its row is removed. `chore/branch-audit` is left out on purpose, since it is this audit's own branch and a different kind of work. |
| `Associated Milestone` | The [GitHub Milestone](https://github.com/Voting-Rights-Code/Equitable-Polling-Locations/milestones) the work belongs to. Blank if none. One exception: **`CVAP integration` is not a GitHub milestone.** It is a project that predates the milestone convention, added by hand so `feature/CVAP` and `feature/279-distance-data-census-type` are grouped. |
| `Status` | `merged` (the work landed, even where git still calls the branch unmerged; see below), `not merged`, `epic branch`, or `TRUNK` (`main`, `dev`). |
| `Merge notes` | Where it merged (`dev`, `dev/main`, or the epic it merged into), its open PR, or why it is being retired (`superseded on dev/main`, `stale`, `duplicate`, `one off script`). |
| `Author` | Who owns the branch. |
| `Final action` | `Keep`, `Delete`, or `DECIDE` (still needs a call). |

Totals on 2026-09-21: **65 rows** (66 branches on `origin`, minus this audit's
branch).

| Status | Keep | Delete | DECIDE |
|---|---|---|---|
| `TRUNK` | 2 | | |
| `epic branch` | 4 | | |
| `merged` | 1 | 33 | |
| `not merged` | 13 | 11 | 1 |

The one `merged` branch marked Keep is `ARCHIVE/original_code`.

## Where things stand

### Open PRs — 11

| PR | Branch → base | Author | Notes |
|---|---|---|---|
| #54 | `feature/modular-distance-calculations` → `main` | orthorhombic | draft, opened 2024-09 |
| #56 | `OSM_GMaps_Compare` → `main` | jmlar | outside contributor, opened 2024-10 |
| #198 | `feature/CVAP` → `main` | Amasus | epic |
| #321 | `feature/driving-distance-tools` → `dev` | abd1tus | epic; in review |
| #329 | `feature/276-R-clean-up` → `feature/optimization_output_maps` | Amasus | root of the Monongalia R stack, see below |
| #330 | `fix/precinct-nearest-neighbor-drift` → `feature/276-R-clean-up` | antisocialscientist | R stack |
| #332 | `feature/generalize_storage.R` → `feature/276-R-clean-up` | Amasus | R stack |
| #334 | `fix/na-blank-normalization` → `feature/276-R-clean-up` | antisocialscientist | R stack |
| #341 | `fix/335-manifest-tree-relative` → `feature/generalize_storage.R` | abd1tus | R stack |
| #343 | `feature/340-precinct-snapshot-upload` → `fix/335-manifest-tree-relative` | abd1tus | R stack |
| #363 | `fix/secret-tests-env-isolation` → `dev` | abd1tus | |

### Epic branches — 4

The repo's hierarchy is `main <- dev <- epic <- feature`. An epic collects
feature branches until the whole piece of work is ready, then goes to `dev` as
one unit. So a feature stacked on an epic cannot merge to `dev` on its own, and
an epic with no PR of its own is not stalled for that reason alone.

| Epic | Milestone | PR |
|---|---|---|
| `delivery/Monongalia_County` | Monongalia County precinct extraction & distance flagging | none yet |
| `feature/CVAP` | CVAP integration (not a GitHub milestone, see above) | #198 → `main` |
| `feature/driving-distance-tools` | `epic-driving-distance-tools` | #321 → `dev` |
| `feature/driving-time-metric` | `epic-driving-time-metric` | none yet |

Delivery branches can deliberately skip `dev`: `delivery/*` branches are
sometimes cut straight from `main` so a client delivery isn't tied to unrelated
`dev` work.

### Kept, not merged, no open PR — 4

Parked work, marked Keep in the CSV:

- `feature/279-distance-data-census-type` (CVAP integration)
- `feature/add_config` (`epic-driving-time-metric`)
- `feature/OSM_GMaps_compare` (distinct from the 2024 `OSM_GMaps_Compare`)
- `feature/RDH-pop` (RDH block-level population data)

### Still to decide — 1

- `feature/docker-backup`: a backup of `feature/docker`.

## Landing the Monongalia R stack — plan as of 2026-09-21

### The remaining Monongalia cleanup stack

These come from PR base refs, and git agrees: each child contains its parent's
tip, except `generalize_storage.R`, which is one commit behind 276 (harmless).

```
dev
└── delivery/Monongalia_County            epic · no PR to dev · 174 ahead / 22 behind dev · last commit 2026-09-08
    └── feature/optimization_output_maps  already merged into the epic (#312, 2026-07-29)
        └── #329 feature/276-R-clean-up   CONFLICTING · 18 commits · assigned Daniel · no reviews
            ├── #330 fix/precinct-nearest-neighbor-drift   clean · 3 commits · assigned Susama (commented)
            │        port-pr330-cleanup is an identical copy (0 commits different either way)
            ├── #334 fix/na-blank-normalization            clean · 1 commit · assigned Susama
            └── #332 feature/generalize_storage.R          clean · 1 commit · assigned Chad
                └── #341 fix/335-manifest-tree-relative    clean · 1 commit · review requested: Susama
                    └── #343 feature/340-precinct-snapshot-upload  clean · 1 commit · review requested: Susama
```

The problem is at the root. #329's base, `feature/optimization_output_maps`, was
already merged into the epic before #329 was opened, so the whole stack is built
on a branch whose work went in by another route.

### How big #329 really is

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

Retargeting #329 will **not** shrink GitHub's number. Its merge base with the epic
is the same commit as with its current base (`3e4ddf2d`). The number drops once
the epic is merged into 276 (step 4 below).

### What the conflict is

An in-memory merge of 276 into the epic conflicts in 14 files.

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

**Twelve generated outputs** in `precinct_analysis_outputs/Monongalia_County_WV/`
(8 heat-map PNGs, 4 flagged-block CSVs). Both sides regenerated them; on the
epic's side that was #323 and #326. Do not hand-merge these: take either side,
then regenerate once the R code is settled.

**Resolution:** take 276's side for both R files, re-add the holes comment, and
regenerate the outputs.

### Order of work

1. **Retarget #329** from `feature/optimization_output_maps` to
   `delivery/Monongalia_County`, *before* anyone deletes
   `feature/optimization_output_maps`. Deleting the base branch of an open PR can
   close that PR.
2. **Delete `port-pr330-cleanup`.** It is an exact copy of #330's branch.
3. **Merge the epic into 276** and resolve as described above, so the review in
   the next step sees the real merged state.
4. **Review and merge #329** into the epic, with a merge commit. This is the
   bottleneck: Daniel has not started the review.
5. **Then the children, parent first, each with a merge commit.** When 276 merges
   and its branch is deleted, GitHub retargets #330, #332 and #334 to the epic.
   Merge #332, then #341, then #343 (the order #341 and #343 ask for); #330 and
   #334 can go in any order.
6. **Later, epic → `dev`.** No PR exists yet, which is normal for an epic. The
   epic is 22 commits behind `dev`, so expect a sync.

Why parent first, with merge commits:

- **Parent first keeps each PR's merged diff equal to its reviewed diff.** Merging
  a child first lands it *inside the parent's branch*, so the parent's PR
  silently grows to include the child's changes after it was reviewed.
- **Merge commits make parent-first safe for the children.** After the parent
  merges, a retargeted child still shows only its own commits. After a squash,
  the child would replay the parent's original commits on top of the squashed
  copy: duplicate changes, and often conflicts.

The underlying rule is "don't change a PR's content after it has been reviewed."
If Daniel would rather review the whole stack as one diff, merging the children
into 276 *before* he starts on #329 also satisfies it.

## How to tell whether a branch's work landed

**This repo has no default merge strategy.** Some PRs are merged with a merge
commit, and some people sometimes squash. That mix is why git alone cannot tell
you whether work landed: a squash-merged branch never becomes an ancestor of its
target, so `git branch --no-merged` reports it as outstanding forever, while a
branch merged with a merge commit next to it looks fine. An earlier pass of this
audit was thrown off by exactly this and misread several branches' lineage.
GitHub PR history is the authoritative source.

Before marking a branch safe to delete, run two tests. Either one passing is
enough; a branch that fails both has commits that exist nowhere else.

1. **Ancestry against the real merge target.** `git merge-base --is-ancestor
   <branch> <target>`. The target is often an epic, not `dev` or `main`.
2. **Tip vs. the SHA GitHub merged.** Compare the branch's current tip to its
   merged PR's `headRefOid`. If they differ, commits were added after the merge.

Each test alone gives wrong answers. Ancestry misses squash merges. The head-SHA
test misses a branch that a later merge into its target swept up. Running both
also catches work committed to a branch *after* it merged: that is how
`feature/optimization_output_maps` was found holding #323 and #326, which never
reached the delivery branch until `9242535f` on 2026-09-08.

Three more checks that each prevented a wrong conclusion:

- **Did the content land?** Paths don't survive the R directory reorg or the
  `python/solver/` restructure. Grep for a distinctive function name or
  identifier from the diff instead.
- **A closed PR is not abandoned work.** The work is often redone on a new branch
  and merged under a new PR. Look for a later merged PR with a similar title, and
  compare dates.
- **Take parent branches from PR base refs.** Guessing parents from merge-base
  proximity was tried and gave confidently wrong answers. Where there is no PR,
  ask a human.

## Sources of truth

1. **[GitHub Milestones](https://github.com/Voting-Rights-Code/Equitable-Polling-Locations/milestones)**
   define the epics. Not branch names, not directory structure.
2. **GitHub PR history** (`gh pr list --state all --head <branch>`) tells you
   whether work shipped.
3. **Git** tells you only which branches exist and when they were committed to.
