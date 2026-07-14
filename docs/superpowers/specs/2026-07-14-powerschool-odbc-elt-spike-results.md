# Spike results: dlt vs Sling for PowerSchool ODBC ingestion

Tracked in [#4398](https://github.com/TEAMSchools/teamster/issues/4398). Spike
PR [#4402](https://github.com/TEAMSchools/teamster/pull/4402). Design:
[2026-07-14-powerschool-odbc-elt-spike-design.md](2026-07-14-powerschool-odbc-elt-spike-design.md).
Plan:
[2026-07-14-powerschool-odbc-elt-spike.md](../plans/2026-07-14-powerschool-odbc-elt-spike.md).

> Status: IN PROGRESS. Cells marked _(pending)_ are not yet measured.

## Environment

- Branch deployment: `kipppaterson` on PR #4402.
- Secrets: `op-ps-db-kipppaterson`, `op-ps-ssh-kipppaterson` created in the
  `dagster-cloud` namespace (Ops, 2026-07-14).
- Scratch datasets: `zz_spike_powerschool_dlt`, `zz_spike_powerschool_sling`
  (project `teamster-332318`).
- Test tables: `students`, `storedgrades`, `assignmentscore`.
- Cursor column: `whenmodified` (merge/upsert on `dcid`).

## Rubric

Legend: ✅ pass · ⚠️ caveat · ❌ fail · _(pending)_ not yet measured.

### `students`

| Dimension               | dlt         | Sling       |
| ----------------------- | ----------- | ----------- |
| Row fidelity            | _(pending)_ | _(pending)_ |
| Type fidelity           | _(pending)_ | _(pending)_ |
| Value fidelity          | _(pending)_ | _(pending)_ |
| Throughput (full load)  | _(pending)_ | _(pending)_ |
| Incremental correctness | _(pending)_ | _(pending)_ |
| Tunnel stability        | _(pending)_ | _(pending)_ |

### `storedgrades`

| Dimension               | dlt         | Sling       |
| ----------------------- | ----------- | ----------- |
| Row fidelity            | _(pending)_ | _(pending)_ |
| Type fidelity           | _(pending)_ | _(pending)_ |
| Value fidelity          | _(pending)_ | _(pending)_ |
| Throughput (full load)  | _(pending)_ | _(pending)_ |
| Incremental correctness | _(pending)_ | _(pending)_ |
| Tunnel stability        | _(pending)_ | _(pending)_ |

### `assignmentscore`

| Dimension               | dlt         | Sling       |
| ----------------------- | ----------- | ----------- |
| Row fidelity            | _(pending)_ | _(pending)_ |
| Type fidelity           | _(pending)_ | _(pending)_ |
| Value fidelity          | _(pending)_ | _(pending)_ |
| Throughput (full load)  | _(pending)_ | _(pending)_ |
| Incremental correctness | _(pending)_ | _(pending)_ |
| Tunnel stability        | _(pending)_ | _(pending)_ |

### Operational feel (cross-table)

| Aspect                         | dlt         | Sling       |
| ------------------------------ | ----------- | ----------- |
| Config size / shape            | _(pending)_ | _(pending)_ |
| Failure-mode legibility (logs) | _(pending)_ | _(pending)_ |
| Fit with existing patterns     | _(pending)_ | _(pending)_ |

## Run log

| Run         | Tool | Table | Kind | Run ID | Wall-clock | Rows | Notes |
| ----------- | ---- | ----- | ---- | ------ | ---------- | ---- | ----- |
| _(pending)_ |      |       |      |        |            |      |       |

## Runtime errors and config adjustments

_(Record here: Oracle schema qualification discovered (unqualified vs `ps`),
Sling `sid` vs `url` connection form, Sling binary download on first run, any
tunnel disconnects, type-cast adapters needed.)_

## Decision

_(Filled in Task 10 after the rubric is complete. Names the pilot tool, the 2-3
rubric rows that decided it, the losing tool's findings, and caveats to carry
into the pilot.)_
