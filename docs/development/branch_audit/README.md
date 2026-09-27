# Branch audit

A working record of every branch on `origin`: what happened to its work, and
whether to keep or delete it. It lives on `chore/branch-audit` and is not meant
for `main`.

Current as of **2026-09-27**, checked against `origin` after `git fetch --prune`
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

Totals on 2026-09-27: **64 rows** (65 branches on `origin`, minus this audit's
branch).

| Status | Keep | Delete | DECIDE |
|---|---|---|---|
| `TRUNK` | 2 | | |
| `epic branch` | 3 | | |
| `merged` | 1 | 33 | |
| `not merged` | 13 | 11 | 1 |

The one `merged` branch marked Keep is `ARCHIVE/original_code`.

## Where things stand

### Open PRs — 9

| PR | Branch → base | Author | Notes |
|---|---|---|---|
| #54 | `feature/modular-distance-calculations` → `main` | orthorhombic | draft, opened 2024-09 |
| #56 | `OSM_GMaps_Compare` → `main` | jmlar | outside contributor, opened 2024-10 |
| #198 | `feature/CVAP` → `main` | Amasus | epic |
| #330 | `fix/precinct-nearest-neighbor-drift` → `delivery/Monongalia_County` | antisocialscientist | R stack |
| #332 | `feature/generalize_storage.R` → `delivery/Monongalia_County` | Amasus | R stack |
| #334 | `fix/na-blank-normalization` → `delivery/Monongalia_County` | antisocialscientist | R stack |
| #341 | `fix/335-manifest-tree-relative` → `feature/generalize_storage.R` | abd1tus | R stack |
| #343 | `feature/340-precinct-snapshot-upload` → `fix/335-manifest-tree-relative` | abd1tus | R stack |
| #363 | `fix/secret-tests-env-isolation` → `dev` | abd1tus | |

The R stack's root moved twice in four days, and both moves were GitHub
retargeting open PRs when their base branch was deleted:

1. **2026-09-23** — #329 merged `feature/276-R-clean-up` into
   `feature/optimization_output_maps` (merge commit `f8ba9a66`), and the head
   branch was deleted, so #330, #332 and #334 retargeted from it to
   `feature/optimization_output_maps`.
2. **2026-09-27** — `feature/optimization_output_maps` fast-forwarded into
   `delivery/Monongalia_County` and was deleted, so the same three PRs
   retargeted again, to the epic. They now go straight to the epic, which is
   where the R stack was always meant to land.

The three PRs were each cut from the original root and are behind the epic by
the R cleanup; expect to merge the epic into them before they go green. The
Monongalia plan lives on the epic.

### Epic branches — 3

The repo's hierarchy is `main <- dev <- epic <- feature`. An epic collects
feature branches until the whole piece of work is ready, then goes to `dev` as
one unit. So a feature stacked on an epic cannot merge to `dev` on its own, and
an epic with no PR of its own is not stalled for that reason alone.

| Epic | Milestone | PR |
|---|---|---|
| `delivery/Monongalia_County` | Monongalia County precinct extraction & distance flagging | none yet |
| `feature/CVAP` | CVAP integration (not a GitHub milestone, see above) | #198 → `main` |
| `feature/driving-time-metric` | `epic-driving-time-metric` | none yet |

`feature/driving-distance-tools` was the fourth epic. It merged to `dev` as #321
on 2026-09-26 (merge commit `96649feb`) and was deleted on `origin`, so it and
its last feature branch, `chore/321-drop-ticket-numbers`, are no longer epic or
open-PR rows. `chore/321-drop-ticket-numbers` still exists on `origin`; its tip
`6c7bc5d6` is an ancestor of `dev`, so it is safe to delete.

Delivery branches can deliberately skip `dev`: `delivery/*` branches are
sometimes cut straight from `main` so a client delivery isn't tied to unrelated
`dev` work.

### Kept, not merged, no open PR — 5

Marked Keep in the CSV. The first is live work, not parked:

- `delivery/Tarrant_County_2026` — PRs #344, #356 and #364 all merged to `main`,
  but `e631aeb1` ("add location_capacity_change") was committed after #364 and
  is not in `main`.

Parked work:

- `feature/279-distance-data-census-type` (CVAP integration)
- `feature/add_config` (`epic-driving-time-metric`)
- `feature/OSM_GMaps_compare` (distinct from the 2024 `OSM_GMaps_Compare`)
- `feature/RDH-pop` (RDH block-level population data)

### Still to decide — 1

- `feature/docker-backup`: a backup of `feature/docker`.

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

## Delete a branch when its work lands, not later

A branch that has delivered but still exists stays a valid PR base, and anything
merged into it afterwards is stranded one hop short of where it was headed.
`feature/optimization_output_maps` is the worked example:

- **2026-07-29** — #312 merged it into `delivery/Monongalia_County`. It was not
  deleted.
- **2026-07-31 to 08-05** — #329, #330, #332 and #334 were opened against it, by
  then an already-delivered branch.
- **2026-08-02** — #323 and #326 merged into it, reaching the epic only via the
  local merge `9242535f` on 09-08.
- **2026-09-23** — #329 merged into it, putting 20 reviewed commits on a branch
  with nothing to carry them onward. The 09-21 audit pass had marked the branch
  `merged` / Delete, which was true of its tip that day.
- **2026-09-27** — merged to the epic and deleted, which retargeted the three
  open PRs to the epic.

Deleting it at the first step would have prevented all of it: GitHub retargets
open PRs when a base branch is deleted, but only when that branch had a merged
PR of its own, and it retargets them to *that* PR's base. #312 satisfied the
condition from 07-29 onward, so any deletion after that date would have sent
#329 to `delivery/Monongalia_County` on its own.

The audit consequence: a row saying `merged` is a statement about the tip on the
day it was checked, not a promise about the branch name. Re-check the tip of any
`merged` branch that still exists before acting on a Delete.

## Sources of truth

1. **[GitHub Milestones](https://github.com/Voting-Rights-Code/Equitable-Polling-Locations/milestones)**
   define the epics. Not branch names, not directory structure.
2. **GitHub PR history** (`gh pr list --state all --head <branch>`) tells you
   whether work shipped.
3. **Git** tells you only which branches exist and when they were committed to.
