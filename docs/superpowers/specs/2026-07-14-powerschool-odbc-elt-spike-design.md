# Spike: dlt vs Sling head-to-head for PowerSchool ODBC ingestion

Tracked in [#4398](https://github.com/TEAMSchools/teamster/issues/4398). Refs
[#3807](https://github.com/TEAMSchools/teamster/issues/3807).

## Background

Paterson's PowerSchool instance now runs on the same hosts as the other regions,
making ODBC (Oracle over an SSH tunnel) available for the first time. The
Couchdrop SFTP feed (`powerschool/sis/sftp/`) can be retired. Issue #3807
proposed replacing the homegrown ODBC stack (~1300 LOC) with Sling, piloting on
kippnewark; it predates the Paterson migration and its dlt-vs-Sling analysis is
outdated.

A July 2026 reassessment (verified against current docs and source for both
tools) found no hard blockers for either. Key facts:

- **SSH tunnel (hard constraint, password auth like Newark/Camden):** Sling
  supports it natively in-process (source-verified, including password auth;
  note it disables host-key verification). dlt has no native support — the
  documented pattern is an external tunnel, i.e. keeping the existing
  `SSHResource.open_ssh_tunnel()` wrapper.
- **Oracle source:** dlt tests and supports the `oracledb` thin dialect; its
  NUMBER-to-float corruption bug was fixed January 2026; type quirks are
  correctable via Python adapter callbacks (pattern already used for
  Illuminate). Sling uses a pure-Go driver; its handling of `NUMBER` with no
  declared scale could not be verified from docs, and it has recent (fixed)
  decimal-scale and CLOB-encoding regressions.
- **Incremental state in ephemeral GKE pods:** Sling is stateless — the
  watermark is `max(update_key)` read from the target table (late-arriving rows
  below the max are skipped; upserts default to DELETE+INSERT). dlt syncs cursor
  state to a `_dlt_pipeline_state` table in the destination and restores it on
  clean start; merge disposition is a true MERGE.
- **Ecosystem:** both `dagster-sling` and `dagster-dlt` are first-party and
  actively maintained. dlt is already in production here (Illuminate, Focus,
  Zendesk). Sling is GPL-3.0 with a single dominant maintainer; its free tier
  runs streams sequentially.

Two questions cannot be settled from documentation and motivate this spike:

1. **Type fidelity:** what BigQuery types does each tool actually produce from
   Oracle `NUMBER` (no declared scale), `DATE`, and CLOB columns?
2. **Throughput:** real wall-clock through the password-auth SSH tunnel for a
   gradebook-scale table.

## Decisions already made (with the user)

| Decision            | Choice                                                                              |
| ------------------- | ----------------------------------------------------------------------------------- |
| Pilot goal          | Template for all regions — winner later replaces the Newark/Camden/Miami ODBC stack |
| Pilot table scope   | Parity with ODBC districts (includes gradebook tables), not just the SFTP 27        |
| Landing destination | Direct to BigQuery (no GCS/Avro layer)                                              |
| Method              | Head-to-head spike on Paterson before committing to a tool                          |

## Spike design

### Test tables

Three tables from Paterson's Oracle instance, chosen for risk coverage:

| Table             | Why                                                                             |
| ----------------- | ------------------------------------------------------------------------------- |
| `students`        | Wide; `NUMBER` PKs without declared scale; dates; the table everything joins to |
| `storedgrades`    | Decimal-heavy (GPA points); moderate volume                                     |
| `assignmentscore` | Largest available; incremental keyed on `whenmodified`; throughput stress test  |

### Runs per tool per table

1. **Full load** into a scratch BigQuery dataset (`zz_spike_powerschool_dlt` /
   `zz_spike_powerschool_sling`) through the password-auth SSH tunnel.
2. **Incremental follow-up run** keyed on `whenmodified` (or
   `transaction_date`), executed in a fresh pod, to observe watermark recovery
   and idempotency.

### Rubric

| Dimension               | How measured                                                                      |
| ----------------------- | --------------------------------------------------------------------------------- |
| Row fidelity            | `COUNT(*)` vs Oracle source; PK-level anti-join between the two tools' outputs    |
| Type fidelity           | `INFORMATION_SCHEMA.COLUMNS` diff — `NUMBER` (no scale), Oracle `DATE`, CLOB      |
| Value fidelity          | Sampled row-level diff on decimal and date columns across the two tools           |
| Throughput              | Wall-clock per full load, same tunnel, same table                                 |
| Incremental correctness | Second run loads only changed rows; no duplicates; watermark survives a fresh pod |
| Tunnel stability        | Disconnects/retries observed during the `assignmentscore` load                    |
| Operational feel        | Config LOC; failure-mode legibility in Dagster logs                               |

### Implementation sketch

- **dlt side:** a throwaway factory modeled on
  `libraries/dlt/illuminate/assets.py` — `sql_database` source with the
  `oracledb` thin dialect, `backend="pyarrow"`, per-table `@dlt_assets`,
  incremental cursor on `whenmodified`, `write_disposition="merge"` for the
  incremental run. Pipeline run wrapped in the existing
  `SSHResource.open_ssh_tunnel()`.
- **Sling side:** a `replication.yaml` with the three streams plus
  `@sling_assets` and a `SlingConnectionResource` whose Oracle connection sets
  `ssh_tunnel` with password auth. `mode: incremental` with
  `update_key: whenmodified` for the follow-up runs.
- **Credentials:** Paterson ODBC and SSH credentials added as branch-deployment
  secrets, mirroring the shape used by kippnewark (host, port, service name,
  user, password; SSH host, port, user, password).
- **Execution:** branch deployment on GKE (the Codespace cannot reach the
  PowerSchool SSH host). Spike assets live only on this branch and are never
  merged; runs are launched manually from the branch deployment.

### Deliverables

1. Spike assets on this branch (dlt factory + Sling replication config for the
   same three tables).
2. A results write-up in a sibling file
   (`2026-07-14-powerschool-odbc-elt-spike-results.md`) with the rubric filled
   in and a tool decision.
3. Issue #3807 rewritten to reflect the winner: Paterson-first pilot retiring
   `sis/sftp/`, parity table scope, direct-to-BigQuery landing, then
   near-mechanical translation to the other regions.

### Out of scope

- dbt source rework (the shared `src/dbt/powerschool` package has `odbc/` and
  `sftp/` external-table source flavors; a third direct-to-BigQuery flavor is
  pilot work, not spike work)
- Retiring the Couchdrop feed
- Any change to kippnewark, kippcamden, or kippmiami
- Sling Cloud / CLI Pro features (`SLING_STATE`, parallel streams) — the spike
  evaluates the free CLI only

## Success criteria

The spike is done when every rubric cell is filled for both tools on all three
tables (or a blocker is documented that makes a cell unreachable — itself a
decisive finding), and a tool recommendation with rationale is written up and
reflected in a rewritten #3807.
