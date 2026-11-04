# Spike results: dlt vs Sling for PowerSchool ODBC ingestion

Tracked in [#4398](https://github.com/TEAMSchools/teamster/issues/4398). Spike
PR [#4402](https://github.com/TEAMSchools/teamster/pull/4402). Design:
[2026-07-14-powerschool-odbc-elt-spike-design.md](2026-07-14-powerschool-odbc-elt-spike-design.md).
Plan:
[2026-07-14-powerschool-odbc-elt-spike.md](../plans/2026-07-14-powerschool-odbc-elt-spike.md).

> Status: COMPLETE. Recommendation: **pilot dlt** (see _Decision_).

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

Legend: ✅ pass · ⚠️ caveat · ❌ fail. Verdicts are consistent across the three
test tables except where noted. Dimensions were measured on the table best
suited to each (row/value fidelity on all three; timezone, incremental, and cost
on `assignmentscore`). Details for each row are in _Additional findings_ below.

### Data fidelity

| Dimension                      | dlt | Sling | Notes                                                                                                                                                                                                                                                                                       |
| ------------------------------ | --- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Row fidelity                   | ✅  | ✅    | Exact, all 3 tables: 1,039 / 11,498 / 270,434 (dlt = Sling)                                                                                                                                                                                                                                 |
| Column set                     | ✅  | ✅    | 155 cols on `students`, identical names; neither injects metadata columns                                                                                                                                                                                                                   |
| Value fidelity (non-timestamp) | ✅  | ✅    | 0 mismatches, incl. 612 newline-laden `storedgrades` free-text comments                                                                                                                                                                                                                     |
| Value fidelity (timestamp)     | ✅  | ❌    | **Sling shifts every `TIMESTAMP` +4h** (fixed offset, not DST-aware); dlt preserves the source wall-clock and matches the incumbent                                                                                                                                                         |
| Type fidelity                  | ⚠️  | ⚠️    | Both flatten the incumbent numeric `STRUCT`-union to scalars (a simplification). dlt preserves precision/length (`NUMERIC(10)`, `FLOAT64` decimals — latent float risk); Sling emits idiomatic `INT64`/`NUMERIC`. Neither matches incumbent types exactly — `stg_` rework needed either way |

### Throughput / incremental / operational

| Dimension               | dlt      | Sling    | Notes                                                                                                                                                      |
| ----------------------- | -------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Throughput (full load)  | ✅       | ⚠️       | Low signal at spike volumes. Sling re-downloads its Go binary per pod (~40s) every run; dlt has no such step                                               |
| Incremental correctness | ✅       | ✅       | Both no-dupe on re-run. dlt `>=` + boundary dedup (state watermark); Sling strict `>` (target-derived watermark, boundary-tie miss risk on coarse cursors) |
| Tunnel stability        | ✅       | ✅       | Both connected first try; Sling's native tunnel reached the legacy host                                                                                    |
| SSH tunnel capability   | ⚠️       | ✅       | Sling has a first-class in-process tunnel; dlt has none (needs external — we already run the `sshpass` wrapper it would reuse)                             |
| Failure-mode legibility | ✅       | ✅       | Both surfaced clear errors in run logs                                                                                                                     |
| Fit with existing repo  | ✅       | ⚠️       | dlt extends the `illuminate` dlt pattern (keyless ADC, pyarrow, per-table partitioned assets); Sling is a new tool/dependency                              |
| Adjustments to run      | ✅ **1** | ⚠️ **4** | dlt: `schema="ps"`. Sling: per-table `update_key`, `service_name` vs `sid`, omit `gc_bucket`, `format=parquet`                                             |

## Run log

| Tool  | Table             | Kind           | Rows      | Wall-clock     | Notes                                            |
| ----- | ----------------- | -------------- | --------- | -------------- | ------------------------------------------------ |
| dlt   | `students`        | full           | 1,039     | —              | keyless load-job, no GCS                         |
| dlt   | `storedgrades`    | full           | 11,498    | 76s            | ran concurrently (throughput not isolated)       |
| dlt   | `assignmentscore` | full           | 270,434   | 147s           | ran concurrently                                 |
| dlt   | `assignmentscore` | incremental    | 0 extract | 6.4s           | cursor no-op; **no full re-read** of 270k        |
| Sling | `students`        | full           | 1,039     | 61s            | incl. binary download                            |
| Sling | `assignmentscore` | full           | 270,434   | 316s (855 r/s) | ran ~isolated                                    |
| Sling | `storedgrades`    | full (parquet) | 11,498    | —              | after CSV→parquet fix; value-clean               |
| Sling | `students`        | incremental    | 0         | ~46s           | strict `>` no-op                                 |
| Sling | `assignmentscore` | incremental    | 0         | ~46s           | strict `>` no-op                                 |
| Sling | `assignmentscore` | forced delta   | 17,850    | 67s (266 r/s)  | watermark-from-target re-pull → restored 270,434 |

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

### Second run (`students`) — dlt loaded; Sling blocked on GCS-staging auth

After the per-table cursor + `schema="ps"` fixes, the second run split the two
tools cleanly — a **genuine, decision-relevant tool difference**, not a
spike-config bug:

- **dlt: PASS.** `dlt/students` loaded 1,039 rows into
  `zz_spike_powerschool_dlt.students` with zero credential config. dlt's
  BigQuery destination uploads files directly through the BigQuery load-job API
  — it **never touches GCS** — so pure ADC (our keyless GKE Workload Identity)
  was sufficient. The residual `transaction_date` case-sensitivity concern did
  **not** materialize: Sling accepted the lowercase `update_key` (it got past
  `getting checkpoint value (transaction_date)` and
  `created table students_tmp`).
- **Sling: FAIL** at GCS staging —
  `Could not connect to GS Storage: dialing: multiple credential options provided`.

Root cause (traced, not our config): Sling loads to BigQuery by staging through
a GCS bucket (`gc_bucket`), which needs a **separate** GCS client. On our
keyless Workload Identity env (no key file, no `GOOGLE_APPLICATION_CREDENTIALS`
— confirmed: `BIGQUERY_RESOURCE`/`GCS_RESOURCE` use bare `project=`, cluster is
Autopilot with `serviceAccountName: ~`), Sling's `fs_google.go` ADC branch does
`google.FindDefaultCredentials()` + `option.WithCredentials(creds)` while the
bundled google-cloud-go storage client **also** auto-detects ADC —
`google.golang.org/api >= v0.258.0` rejects the pair. The `WithHTTPClient`
workaround that avoids this exists **only** on the explicit-key branch; both the
deployed `sling==1.5.20` and current `main` still use the single-option ADC path
(latest release is only 1.5.21), so no version bump helps. Fixing it "properly"
would mean mounting a long-lived GCP SA key — against the keyless posture the
rest of the stack (dbt, dagster, dlt) runs on.

Fix applied (keeps the comparison fair without a key): **omit `gc_bucket`**.
`gc_bucket` is documented as optional/recommended; without it Sling loads
through the BigQuery client directly (the same keyless load-job path dlt uses),
bypassing the GCS filesys entirely. Slower than GCS bulk staging, irrelevant at
spike volumes.

Decision-relevant takeaways regardless of the workaround:

- dlt inherits our keyless ADC model with no config and no GCS dependency.
- Sling's **recommended** BigQuery fast path (GCS staging) is broken on keyless
  Workload Identity and would require introducing an SA key; its keyless
  fallback works but forfeits the bulk-load throughput advantage — the exact
  axis a "template for all regions" decision turns on.

### Third run (all 3 Sling streams) — gc_bucket fix worked; CSV staging broke on text

Omitting `gc_bucket` **resolved** the credential conflict: Sling loaded via
`importing into bigquery via local storage` (no GCS client). Two of three
streams succeeded; the third exposed a **fourth** Sling-specific issue.

| Stream            | Result | Rows    | Sling wall-clock      |
| ----------------- | ------ | ------- | --------------------- |
| `students`        | ✅     | 1,039   | 61s (17 r/s, 1.3 MB)  |
| `storedgrades`    | ❌     | —       | CSV parse failure     |
| `assignmentscore` | ✅     | 270,434 | 316s (855 r/s, 71 MB) |

- **Row-count agreement (positive):** Sling `students` = 1,039, identical to
  dlt's 1,039 — first head-to-head row-fidelity data point.
- **CSV staging failure (Sling issue #3, `storedgrades`):** Sling's keyless
  BigQuery load stages through **CSV**, which failed
  `CSV processing encountered too many errors ... Rows: 11492; errors: 6; max bad: 0`.
  PowerSchool `storedgrades` free-text columns (course names, comments) carry
  embedded newlines/quotes/delimiters that break CSV; `maxBadRecords=0` fails
  the whole load on any glitch. Fix (Sling's own recommendation):
  `target_options.format=parquet`. dlt avoids this entirely via its native
  pyarrow backend.
- **Table-name casing (note, not a blocker):** Sling created `STUDENTS` /
  `ASSIGNMENTSCORE` (uppercase, from the Oracle identifier) whereas dlt created
  lowercase `students`. Real implementation would need explicit lowercasing of
  the `object` name to match our snake_case convention; recorded here, not fixed
  in the spike.

Running tally of tool friction: dlt required **1** adjustment (`schema="ps"`);
Sling required **4** (per-table `update_key`, `service_name` vs `sid`, omit
`gc_bucket`, `format=parquet`). Each Sling item was legitimately fixable, but
the accumulation is itself the signal — dlt fit our keyless/pyarrow stack out of
the box; Sling needed a workaround at nearly every layer.

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

## Additional findings

### Timezone: Sling shifts every timestamp +4h (correctness)

The same Oracle source lands `whenmodified` **4h apart** between the tools:
Sling `2026-06-18 14:31` UTC vs dlt `10:31` UTC. Characterized on
`assignmentscore` (270,434 rows joined on `assignmentscoreid`):

- The offset is a **uniform +240 min on every row**, spanning 2023-09 → 2026-06
  — including winter (EST) rows. A real `America/New_York` conversion would be
  +300 min (5h) in winter, so this is a **fixed offset, not a DST-aware tz
  conversion**.
- Hour-of-day clustering vs the incumbent (Newark
  `src_powerschool__assignmentscore`, 31.5M rows, avg hour 13.9, 72% in
  ET-daytime 6–17h): dlt (avg 14.5, 58% in 6–17h) clusters with the incumbent;
  Sling (shifted later, wraps past midnight) does not.
- **dlt preserves the Oracle wall-clock (naive-stored-as-UTC) and matches the
  incumbent convention; Sling silently shifts all timestamps +4h.** The load
  reports success while doing it — this would corrupt time-of-day analytics,
  freshness checks, and any cursor/join/filter on time. Fixable in Sling
  (session tz / source options), but silent-by-default and another thing to hunt
  for.

### Incremental: correct on both, different watermark semantics

Neither tool re-reads the full table on an incremental run (dlt
`assignmentscore` re-run: **6.4s, 0 rows extracted**; the cursor filter is
pushed server-side to Oracle). Both are no-dupe. The mechanics differ:

- **dlt** stores the watermark as `last_value` in pipeline state and filters
  `cursor >= last_value` (inclusive, `range_start="closed"`), then dedups the
  boundary rows by `primary_key` — so a late row sharing the exact watermark is
  still caught.
- **Sling** recomputes the watermark as `MAX(update_key)` from the **target**
  each run and filters `update_key > watermark` (strict). A row stamped with
  exactly the watermark that wasn't already loaded is **silently skipped**.

For our fine-grained cursors (`transaction_date` on `students` is all-distinct)
the tie risk is negligible; for a coarse cursor it is real. dlt's
inclusive+dedup is the more defensive default.

### SSH tunnel: Sling has a native one, dlt doesn't

dlt (`sql_database`) has **no** SSH-tunnel feature — you tunnel externally and
point it at localhost, which the spike does via the repo's
`SSHResource.open_ssh_tunnel()` (the `sshpass` wrapper the incumbent ODBC
resource already uses). Sling has a first-class in-process `ssh_tunnel` (Go
`crypto/ssh`), which reached the legacy host on the first try. So **Sling wins
the tunnel dimension** — neutralized for us only because we already run that
wrapper.

Learning worth acting on regardless of tool: the `sshpass` subprocess (+ mounted
password file + readiness race) is legacy friction. `SSHResource` already uses
`paramiko` (with legacy `ssh-rsa` re-enabled) for its SFTP methods; the tunnel
could move to an in-process paramiko forward reading the password from an env
var — Sling's model, but keeping host-key verification (better than Sling's
`InsecureIgnoreHostKey`). Filed as a follow-up.

### Parallelism: same capability, different idiom

Both `@dlt_assets` and `@sling_assets` are `multi_asset(can_subset=True)` — one
op per decorator. Dagster-level parallelism comes from how many ops you split
into, identical for both. The spike's dlt-parallel / Sling-serial split was a
structuring choice (3 per-table dlt pipelines vs 1 Sling replication with 3
streams), not a capability gap. In-op, Sling parallelizes streams with
`SLING_THREADS`; dlt with its extract/load worker pools. dlt's per-table
pipeline idiom maps onto Dagster partitions more naturally than Sling's
single-config model.

### Ingestion cost + strategy (BigQuery cost is real; Oracle reads are free)

Measured from the spike's own BigQuery job history (on-demand pricing — the 10
MB per-query floor is visible):

- **Sling's incremental upsert = `DELETE` + `INSERT` + heavy introspection.**
  Per run on the 67 MB `assignmentscore`: `LOAD` delta→tmp (**free**),
  `DELETE FROM target WHERE EXISTS(...)` (**~63 MB — scans the whole target**),
  `INSERT` (~20 MB), plus ~7 `INFORMATION_SCHEMA` queries at the 10 MB floor
  (~80 MB). The `DELETE` is **delta-size-independent** — it bills ~target-size
  every run, so it scales badly to multi-GB tables.
- **`LOAD` jobs bill 0.** Full refresh (truncate + load) and partition overwrite
  are near-free on BigQuery.
- **Clustering does NOT rescue the merge** (measured): identical `DELETE`
  copies, clustered vs unclustered on `assignmentscoreid`, both billed **68 MB**
  — no pruning. BigQuery does not prune a dynamic-join `DELETE … WHERE EXISTS`
  by the staging key range without a **static** predicate; the tools emit
  generic dynamic-join DML, so clustering is inert here.
- **Partitioning + a static windowed predicate DOES prune** (measured, dry-run):
  on a `PARTITION BY DATE(whenmodified)` copy,
  `WHERE DATE(whenmodified) >= '2026-06-01'` scanned **4.3 MB vs 67 MB**
  unpartitioned (~15×).

Cost ranking, given free Oracle reads: **full refresh (free `LOAD`) ≈
partitioned windowed replace (free `LOAD`, ~15× pruned reads) ≪ row-level merge
(bills ≥ target-size every run)**.

Caveat: **neither dlt nor Sling does partition-scoped replace natively** — dlt
`replace` is whole-table; the incumbent's windowed replace is its
GCS-external-table + Dagster-partition architecture. Realizing it with a native
BQ table is pilot design work (partition-decorator `LOAD`s / Dagster-partitioned
assets), and it fits dlt's per-table partitioned-asset idiom better than
Sling's.

Recommended pilot ingestion strategy (per-table): **full refresh** small/medium
tables (free, and dodges the cursor edge cases); **partitioned windowed
replace** for large tables; **row-level merge** only where genuinely
unavoidable. All three avoid the merge scan that dominates BigQuery cost.

## Decision

**Pilot dlt.**

The two tools tie on the fidelity that matters most — **row and non-timestamp
value fidelity are exact** — and Sling is a more capable tool than its rocky
start suggested (native SSH tunnel, more idiomatic scalar types). But the
decision for a _template for all regions_ turns on correctness-of-defaults and
operational fit, and dlt leads decisively on both:

1. **Timestamp correctness.** Sling silently shifts every `TIMESTAMP` +4h; dlt
   preserves the wall-clock and matches the incumbent. This alone is a strong
   mark against adopting Sling as a drop-in.
2. **Robust defaults on real data.** Sling's default CSV staging corrupted-then-
   failed on PowerSchool free-text (needed `parquet`); its recommended GCS
   fast-path is broken on our keyless Workload Identity (needed a workaround);
   its strict-`>` cursor risks boundary-tie misses. dlt's pyarrow / keyless-ADC
   / inclusive-cursor defaults handled all of this out of the box.
3. **Fit + friction.** dlt needed **1** adjustment and extends the existing
   `illuminate` dlt pattern; Sling needed **4** and is a new dependency. dlt's
   per-table pipeline idiom also maps onto the partitioned ingestion strategy
   the cost analysis recommends.

Sling's genuine wins (native tunnel, idiomatic types) don't offset these: the
tunnel is neutralized because we already run the wrapper dlt reuses, and the
type edge is closable via dlt reflection config while Sling's timestamp shift is
a silent correctness bug.

### Caveats to carry into the dlt pilot

- Regenerate the `stg_` layer to read scalar numerics (the incumbent's
  `STRUCT`-union unpacking goes away) — required for either tool.
- Configure dlt reflection so decimals land as `NUMERIC`, not `FLOAT64` (avoid
  float drift on GPA/balance columns).
- dlt lands dates as `TIMESTAMP` vs incumbent `DATE` — add the cast in staging.
- Adopt the ingestion strategy above (full refresh / partitioned replace; avoid
  row-merge); partition-scoped replace is dlt-pilot design work, not a native
  flag.
- Retire the `sshpass` tunnel for an in-process paramiko forward (separate
  follow-up).
