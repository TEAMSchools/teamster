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
- Test tables + per-table cursor / merge key (from the working ODBC pipeline,
  verified against `INFORMATION_SCHEMA`):
  - `students` — cursor `transaction_date`, key `dcid`
  - `storedgrades` — cursor `transaction_date`, key `dcid`
  - `assignmentscore` — cursor `whenmodified`, key `assignmentscoreid`

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

### First run (both tools, `students`) — connection worked, table/cursor wrong

Both tools **connected successfully** — tunnel + Oracle auth + BigQuery all
worked on the first attempt. Notably, **Sling's native `ssh_tunnel` reached the
PowerSchool host** ("connecting to source database (oracle)" ✓), so the
`ssh-rsa` host-key concern (below) did NOT materialize — a positive data point
for Sling. Both then failed at table/column resolution, from a spike-config bug
(shared here, not a tool differentiator):

- **Wrong cursor column (both tools).** The spike hardcoded one cursor
  (`whenmodified`) for all three tables. Verified against the working ODBC
  pipeline + `INFORMATION_SCHEMA`: `students` and `storedgrades` have
  `transaction_date` but **no** `whenmodified`; `assignmentscore` has
  `whenmodified` and keys on `assignmentscoreid` (no `dcid`). Sling failed "did
  not find update_key: whenmodified" on `students`. Fixed: per-table
  `SPIKE_TABLES` mapping (students/storedgrades → transaction_date/dcid,
  assignmentscore → whenmodified/assignmentscoreid).
- **dlt needed explicit schema (dlt only).** dlt raised
  `sqlalchemy.exc.NoSuchTableError: students` — SQLAlchemy reflection looks in
  the login user's own schema, and the tables are owned by `ps`. (The ODBC
  pipeline dodges this with unqualified raw SQL via Oracle synonym resolution;
  Sling already reached `ps.students` because its streams were qualified.)
  Fixed: `sql_table(..., schema="ps")`. This is a genuine tool difference worth
  noting — Sling's stream qualification made the owner schema explicit up front;
  dlt's reflection needed it added.

### Known items to watch / adjustments made (pre-run)

- **Sling Oracle connect key (fixed pre-run):** initial code used `sid=` for
  `PS_DB_DATABASE`, but that value is a **service name** (the prod ODBC resource
  passes it as `service_name`). Changed to `service_name=` — Sling's Oracle
  connector accepts it as a distinct property
  ([docs](https://docs.slingdata.io/connections/database-connections/oracle)).
  Using `sid=` would have failed with ORA-12514 and made Sling look broken.
  (Caught by the PR `claude-review` bot.)
- **SSH host-key algorithm asymmetry (watch at run):** the dlt path uses the
  repo's `sshpass` wrapper, which sets `-oHostKeyAlgorithms=+ssh-rsa` /
  `accept-new` for legacy PowerSchool SSH hosts. Sling's native `ssh_tunnel`
  uses Go's `crypto/ssh` with `InsecureIgnoreHostKey()` — it skips host-key
  _verification_ entirely, so it should sidestep a legacy `ssh-rsa` host key,
  BUT if the server only offers `ssh-rsa` as a host-key _algorithm_ and Go's
  client has dropped it from negotiation, the Sling tunnel could fail at KEX
  where dlt succeeds. If the Sling side fails to connect, record it as a
  tunnel-stack artifact (not a Sling ingestion deficiency) — though "can't
  tunnel to our host out of the box" is itself a decision-relevant finding.
- **Oracle schema qualification (watch at run):** dlt uses the unqualified table
  name; Sling streams are qualified `ps.<table>`. If dlt reflection fails "table
  not found," add `schema="ps"` to `sql_table(...)`.
- **Sling binary (watch at first run):** the linux/amd64 `sling` wheel
  lazy-downloads its binary on first import; the first Sling materialization may
  include one-time download overhead — exclude it from the throughput figure or
  re-run for a clean number.
- _(add: any tunnel disconnects, type-cast adapters needed.)_

## Decision

_(Filled in Task 10 after the rubric is complete. Names the pilot tool, the 2-3
rubric rows that decided it, the losing tool's findings, and caveats to carry
into the pilot.)_
