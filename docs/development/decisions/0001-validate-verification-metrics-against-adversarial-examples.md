# 0001: Validate verification/diagnostic metrics against adversarial examples before trusting them

## Status

Accepted

## Context

This is a data science project; a recurring task shape is "design a check that tells us whether some derived data is correct" (e.g., does a county's precincts decompose cleanly into its census blocks). These checks are usually novel — there's no existing, proven implementation to copy — which means the check's *design* is itself unverified the first time it's written, separately from whether its *code* is bug-free.

While building a precinct/census-block decomposition check (issue #267), the original design compared a precinct's polygon against the union of census blocks that had already been **cropped to that precinct's boundary**. That comparison is tautologically near-zero by construction: clipping a block to a precinct before checking whether it fits inside that precinct erases the very evidence (a block straddling the boundary) the check was meant to surface. The check ran successfully, returned small, "clean" numbers for all 44 precincts, and was reported as passing — but it could never have reported otherwise, even for badly-decomposed data. The flaw was only found afterward, by hand-tracing what the check should output for a constructed case ("a block split 50/50 between two precincts").

This is a general risk for diagnostic/verification code, not specific to spatial geometry: a check that compares a value to a transformed copy of itself, or whose inputs are forced into agreement before the comparison runs, can look correct (it runs, it produces numbers, the numbers look small) while being structurally incapable of detecting the problem it exists to catch.

## Decision

Before relying on (or approving) any new verification/diagnostic check, construct a worked example representing the specific failure the check is meant to catch, and trace through what the check's computation would actually output for that example. Do this before — or immediately after — writing the implementation, not only after the real data has already returned a "passing" result.

In tickets, specs, and PR descriptions that introduce a new check, mark it explicitly as one of:
- **Validated** — a worked failure-case example was traced through the design and it produces the expected flagging output.
- **Unvalidated** — the design is a best guess; it should not be treated as confirmed until someone traces a failure case through it.

This applies equally to checks designed by a human contributor and to those designed with AI assistance (e.g., Claude Code) — the failure mode is in the design, not in who or what wrote it.

## Consequences

- Adds a small amount of upfront design time to tickets that introduce a new check or metric. Tickets that only reuse an already-validated check, or that are pure data plumbing (reading files, wiring config), don't need this step.
- Catches tautological or otherwise uninformative checks before time is spent implementing and running them against real data.
- Makes it easier for a reviewer (human or AI) to tell, at a glance, which parts of a spec are settled and which are still a guess that needs scrutiny.
