# 0002: Persist the driving-time metric and duration in BigQuery via nullable columns

## Status

Accepted

## Context

Epic #227 adds `driving_time` as an alternate travel metric alongside `haversine` and `driving_distance`. Phases 1–2 made it work on the CSV path: Open Route Service emits both distance and duration, and the solver selects the configured metric by aliasing `duration_s` into the working `distance_m` column based on a `metric` config field. Phase 3 (#230) extends this to the BigQuery/DB path.

Two facts about the DB path shaped the design:

1. **A DB model run loads its config from the database.** `model_run_db_cli` reads configs via `create_polling_model_config`, which copies only fields that exist as columns on `model_configs`. The `metric` field was added to the YAML/solver in Phase 2 (#229) but never persisted to the DB, so a DB-loaded config had `metric = None` and a `driving_time` run would silently fall back to the stored driving *distance*.
2. **The DB run reads distances from the pre-built `distance_data` table**, not the raw `driving_distances` table. So the duration value has to reach `distance_data`, not only `driving_distances`.

## Decision

1. Persist duration as a nullable **`duration_s`** (raw ORS seconds) column on both `driving_distances` and `distance_data`. The name is `duration_s`, matching the CSV column, the `DISTANCE_DURATION_S` constant, and #230's title. Per the project lead's decision on #294, durations are stored in **seconds**, not minutes: seconds keeps every real duration >= 1, so `log_distance: true` on the `driving_time` metric never produces a negative log, and it matches the sibling `distance_m` unit convention (raw units, no scaling). This supersedes an earlier version of this ADR that chose `duration_min` (minutes) for CSV-column-name symmetry; that earlier choice is what produced the negative-log bug. The import layer maps CSV↔DB columns *by name*, so the DB column must still match the CSV column exactly or the value is silently dropped.
2. Persist the metric as a nullable **`metric`** (String) column on `model_configs`, completing the config-field persistence that Phase 2 (#229) implemented only on the CSV/solver side. Without it, `driving_time` cannot survive the config DB round-trip.
3. **All three columns are nullable** for back-compat: existing rows and every `haversine`/`driving_distance` row stay valid with NULL. `metric = None` makes `apply_metric` a no-op, and `distance_m` already holds the correct value for those runs.
4. **No CLI/build logic changes.** The import/build/read pipeline is model-driven (it keys off the ORM columns), so declaring the columns is sufficient for the values to flow import → build → read → `apply_metric`. Verified by unit tests and an `e2e_db` round-trip plus a real `driving_time` DB solve.

## Consequences

- **Config id changes for re-imported configs.** `ModelConfig.generate_id()` hashes all columns, so adding `metric` changes the computed id for any config re-imported after the migration: the re-import produces a new id and therefore a duplicate `model_configs` row rather than matching the pre-existing one. This is inherent to the config-hash scheme (every added column has this effect) and is accepted — `metric` genuinely distinguishes configs (a `haversine` and a `driving_time` config should hash differently). Configs already stored are unaffected until re-imported.
- **Alembic fork.** The migration (`d1f2a3b4c5d6`) branches off head `25c563b5a292`, the same parent as the concurrent #279 migrations (`d33f00f3c168`, `b7c4e2a9f1d3`). When both branches reach `main`, Alembic will have two heads and needs a one-line merge revision. Applying this migration to a dataset that already carries #279's migrations (as the shared `tests_chad` test dataset did) requires reconciling the Alembic version pointer first.
- **Downgrade is best-effort.** The migration `downgrade` uses `op.drop_column`, whose support on the BigQuery dialect is unverified.

## Alternatives considered

- **Name the column `duration_min` (minutes)**: this was this ADR's original decision, chosen for CSV-column-name symmetry; superseded per the project lead's call on #294 — minutes produces negative values under `log(duration)` for sub-minute cells when `log_distance: true`, which broke the `driving_time` metric.
- **Add duration only to `driving_distances`**: rejected — the DB run reads `distance_data`, so a `driving_time` DB run would not see the duration.
- **Split the `metric`-on-config work into a separate ticket**: considered, but folded in here because #230's own acceptance criterion ("a duration-metric DB run solves") is untestable without it.
