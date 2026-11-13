# Validator: save each comparison's rows once, resume after a stop

Issues: #6410, plus #6411 and #6412 (see _Also in this PR_). Branch:
`cristinabaldor/fix/claude-validator-second-fact-time-dims`, PR #6402.

All validator work from the DDI Suite validation ships in one PR, #6402, which
already carries the second-fact and date fixes (#6401, #6384). The owner chose
one PR: the fresh DDI validation needs every piece, so shipping parts early buys
nothing.

## Intent and why

The Cube validator (`scripts/cube_validation`) checks Cube against a Tableau
dashboard in two long steps: `run` compares every comparison at one warehouse
moment, and `triage` re-runs the stored cause proofs on what `run` found. On the
DDI Suite (#6211) each step takes about 60 to 80 minutes.

Two things go wrong:

- **A stop means starting over.** `run` writes `run.json` only at the end
  (`pipeline.py`, `run`). `triage` keeps nothing between processes. On
  2026-11-13 a triage hit the daily spending cap after about 65 minutes, and
  re-running it would have repeated all 65 minutes. The same happens if the
  codespace stops, the power goes out, or the owner has to leave.
- **Triage is slow because it repeats `run`'s work.** Each proof query inlines
  both full sides of its comparison (the Cube SQL and the dashboard SQL, read as
  of the run's moment) through `unmatched_sql` in `confirm.run_proof`. A proof
  query is about 250,000 characters, about 1,000 stages, about 65 seconds and
  about 116 slot-minutes. `run` already computed those sides once. Measurements
  are on #6410.

The owner wants a validation that is cut off partway to pick up where it
stopped, and a triage fast enough to fit around a meeting.

## Goals

1. `run` saves each comparison's result as it finishes. A stopped `run`, started
   again with the same command, skips the comparisons it finished and continues
   at the same warehouse moment.
2. `run` saves each comparison's unmatched rows, per bucket, to a BigQuery table
   that outlives the process. `triage` and `triage confirm` read those tables
   instead of recomputing both sides.
3. `triage` saves each proof's outcome as it finishes. A stopped `triage` skips
   the proofs it finished.
4. `triage` estimates the cost of every proof it will run before running any,
   and refuses up front if the total would pass the daily cap.
5. `run` compares 4 comparisons at a time, and `triage` runs 4 proofs at a time.
6. `triage` takes `--comparison` (repeatable), like `prove`.

Success: on the DDI view, a full `run` finishes in under 30 minutes and a full
triage of a saved run in under 10; a `run` or `triage` stopped partway and
started again produces the same `run.json` / `triage.json` as an uninterrupted
one. The 30-minute target is an estimate (BigQuery time dominating, slots to
spare); the plan measures it.

## Non-goals

- Changing what a proof means, how causes are recorded, or the decision model.
- Speeding up `prove`, `check-api` or the trace (`triage` without `--no-trace`).
- Sharing saved rows between people. Each saved table belongs to one run.

## Anti-goals (a failure even if it works)

- A resumed run that mixes two warehouse moments or two versions of Cube's SQL
  without saying so. A resume must reconcile exactly what an uninterrupted run
  would have.
- Student-level rows readable by anyone who can read the project. Today's
  session temp tables are private to the person running the validator; the saved
  tables must stay as restricted as the marts they come from.
- Two code paths for the same thing. The session temp-table path
  (`Warehouse.session`, `Warehouse.freeze`, `confirm._freeze`,
  `trace.MAX_QUERY_CHARS` switch) is replaced, not kept beside the new one,
  unless the trace still needs it.

## Constraints

- **The scratch dataset is created once, by the owner, in their terminal.**
  Claude does not run warehouse DDL. The validator creates and replaces tables
  inside that dataset only, as it creates session temp tables today. Proposed:
  `teamster-332318.cube_validation_scratch`, location `US`, default table
  expiration 14 days, read and write limited to the Data Team group. The design
  names the dataset in one constant; the exact `CREATE SCHEMA` statement goes in
  the plan for the owner to run.
- **Resume window is 7 days.** A resumed run reads the warehouse as of the
  original moment through time travel (`timetravel.as_of`), and BigQuery keeps 7
  days of history. Past that, `run` refuses to resume and says to start a new
  run. Inside it, only a run stopped in the last 24 hours resumes on its own;
  see _`run`_.
- **Unmatched rows are student-level PII** (they carry the comparison's grain,
  which includes `student_number`). They stay inside BigQuery: no local copy in
  the run cache beyond what `run` already writes.
- **Spending cap.** Every query still counts against `--max-usd` and
  `--max-usd-per-day` through `Warehouse.budget` and the daily ledger, from
  concurrent workers too.
- Tests run offline against duckdb
  (`uv run --with duckdb pytest tests/scripts/cube_validation/`); live behavior
  is checked with a throwaway runner under `tests/`.

## Approaches

- **A. Saved tables in a scratch dataset (picked).** `run` writes each
  comparison's unmatched rows to real tables with a 14-day expiry; checkpoints
  live in the run cache and on the tables. Any process can read them, several
  queries at once, until they expire. Costs one new dataset.
- **B. BigQuery's own 24-hour query results.** Proofs read `run`'s reconcile
  results from the job's anonymous result table. No new dataset, but the results
  expire after about 24 hours (a fix shipped the next day finds them gone), and
  the reconcile result may not hold the row-level data proofs need. Rejected.
- **C. Keep session temp tables, always freeze, cache outcomes locally.**
  Smallest change, but a bucket usually has one proof, so freezing saves little;
  the session runs 1 query at a time, so no concurrency; and the tables vanish
  with the process. Rejected.

The owner picked A after weighing what happens on a power cut or codespace stop:
under A, at most the comparison in progress is redone, if the owner returns
within 7 days.

## Design

### Identity of saved work

A run is identified by its view and its moment (`Build.start`, `Build.end`). A
comparison's saved work is valid for a run only if its **fingerprint** matches:
a hash of the comparison's config entry and both sides' SQL as `run` built them
(`_Sides.sql`, `_Sides.fingerprints`). A Cube deploy or a YAML edit changes the
fingerprint and makes that comparison's saved work stale.

### `run`

- Before comparing, look for an unfinished run of the same view in the cache (a
  run folder with checkpoints and no `run.json`). By the age of its last
  checkpoint:
  - Under 24 hours: resume it, reusing its moment instead of picking a new one,
    and print that it resumed and from when.
  - 24 hours to 7 days: refuse, and say to pass `--resume` (continue at the old
    moment) or `--restart` (start fresh). Either flag settles it.
  - Over 7 days: refuse to resume; `--restart` starts fresh.

  `--moment` overrides all three.

- After each comparison, write a checkpoint to the run folder: that comparison's
  slice of `_Sides` (cells, groups, clauses, sql, fingerprints, moved, cell SQL
  and prices, cell rows, students). On resume, load the checkpoints whose
  fingerprint still matches and compare the rest. A comparison whose fingerprint
  changed is compared again and the change is printed.
- Save each comparison's unmatched rows to one table in the scratch dataset,
  with a `bucket` column (`value_differs`, `dims_differ`, `dashboard_only`,
  `cube_only`). The reconcile already sorts every row into its bucket in one
  query, so it writes the unmatched rows once and the counts come from the same
  statement; one table per bucket would rerun the reconcile per bucket. Labels
  carry the view, run moment, comparison id and fingerprint. The table name is
  derived from the view, moment and comparison (stable, so a re-run replaces
  it).
- Compare 4 comparisons at a time. Each worker builds its comparison's slice and
  returns it; one thread merges slices into `_Sides` and writes the checkpoints,
  so workers share no results. `Warehouse`'s spend counter and the daily ledger
  take a lock, which `triage`'s workers need too.

### Checkpoints: which record decides

A comparison's "done" is recorded in two places, and they can disagree (a table
expired or was dropped; a rebuilt codespace lost the run folder). Each has one
job:

- **The checkpoint file in the run folder decides what `run` skips.** No file
  (or a stale fingerprint) means the comparison runs again and replaces its
  table. An existing table never makes `run` skip a comparison.
- **The table's labels only guard `triage`.** A table whose labels do not match
  the run is refused, never read.

### `triage` and `triage confirm`

- Proofs read the saved table for their comparison, filtered to their bucket, in
  place of `{unmatched}`'s inline SQL. If the table is missing or its label
  fingerprint does not match the run, refuse with "run `run` again for this
  comparison" rather than recomputing inline.
- Before running any proof: list every (proof, comparison) pair to run, dry-run
  them (concurrently, as the trace's dry runs are today), sum the estimates and
  refuse if the total would pass either cap.
- Run proofs 4 at a time. Write each outcome to `triage-progress.json` in the
  run folder as it finishes, keyed by proof file hash, comparison and bucket. A
  later triage of the same run reuses outcomes whose key still matches.
  `triage.json` is written at the end as today.
- `--comparison X` (repeatable) limits the proofs and the open items reported to
  those comparisons.
- Triage still recompiles each comparison's Cube SQL and refuses when it no
  longer matches the run's fingerprint, as `Prepared.row_sides` does today. That
  check is compile-only; the expensive part (reading both sides in BigQuery)
  comes from the saved table. `run` saves, per comparison, the tables only the
  Cube side reads, since `trace._one_moment` needs that set to read them at the
  build end.
- The progress key for a saved proof outcome is the proof file hash, the
  comparison, the bucket, the comparison fingerprint and the set of item ids it
  covered. `reapply` changes which groups are open, so an outcome saved for a
  different item set is not reused.

### Budgets across a resume

- `--max-usd` caps each process, as today. The daily cap (`--max-usd-per-day`)
  still bounds the total across processes.
- Each checkpoint records what its process spent, and `run.json`'s cost is the
  sum, so it reports the true total.
- "Same result" in the success test means the same comparisons, cells, groups
  and open items; cost differs. The anchor and identity checks
  (`_anchors_and_identities`) run once, at the end, on that day's data, as
  today.

### `--restart` and the run folder

`report.save_local` names a run's folder after its moment, so two runs of the
same build share a folder. `--restart` clears that folder's checkpoints and
`triage-progress.json` before starting, so nothing from the old attempt sits
beside the new run.

## Decided by the owner

- Cover both `run` and `triage` in this change.
- Approach A, scratch dataset with auto-expiry.
- Resume after a stop is the main requirement; speed comes second.

- `run` compares 4 comparisons at a time, as `triage` runs 4 proofs: time is a
  goal for both steps.
- Resume on its own only within 24 hours of the last checkpoint; 24 hours to 7
  days needs `--resume` or `--restart`.
- One saved table per comparison, with a `bucket` column.
- The run folder's checkpoint decides what `run` skips; table labels only guard
  `triage`.

## Calls made in the design (owner to check)

- Dataset name, 14-day expiry, Data Team-only access.
- 4 concurrent workers.
- Refuse, rather than silently recompute, when a saved table is missing.
- Remove the session temp-table path once nothing reads it.
- Triage keeps the compile-only Cube SQL check and refuses on a mismatch.
- `--max-usd` stays per process; `run.json` reports total cost across processes.
- `--restart` clears the folder's checkpoints and triage progress.

## Runs saved before this change

No backfill. Runs saved before this change have no saved tables, so the new
triage refuses them and says to run `run` again. The owner is starting the DDI
validation fresh once this ships, so no old run needs to survive, and a backfill
command would be a second code path.

## Also in this PR

Smaller validator fixes found on the same DDI validation. Each lands as its own
commit, small ones first.

- **#6411: confirm cells on a distinct-student share.** `triage confirm --cells`
  rebuilds a rate as the mean of its rows' value column, which never equals a
  share of distinct students, and cannot size a cell whose cuts or `scope` sit
  on columns the reconcile does not group by. Fixed means a bucket comparison
  whose row groups are all proven has its cells confirmed too. Details on the
  issue.
- **#6412: the identifying-column guard.** `confirm._identifies` treats any
  column ending in `_number` as one that can name a student, so a band number is
  refused. Keep the guard strict for real identifiers (`student_number`,
  `employee_number`, an aliased student number) and let category numbers pass. A
  missed identifier is worse than a false refusal.
- **Proof dry-run in `prove --check` (part of #6410).** A proof that reads a dbt
  intermediate model breaks when the model's columns change, and today that
  shows up only when triage runs it. `prove --check` dry-runs each stored proof
  against the warehouse (free) and lists the ones BigQuery rejects, so a broken
  proof is found in seconds.

## Left to the builder

- The exact checkpoint file format and table naming scheme.
- How the reconcile statement writes the table and returns the counts (a
  multi-statement script, or a write followed by a count over the table).
- Thread-safety of the rest of `Warehouse` (client, dry-run cache) under
  concurrent workers.
- Whether the trace keeps any use for session temp tables.
- Updating the `cube-validation` skill and any published docs that describe
  triage's cost or time.
