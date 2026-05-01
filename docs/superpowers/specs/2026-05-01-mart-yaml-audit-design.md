# Mart YAML Audit — Design

Issue: [#3678](https://github.com/TEAMSchools/teamster/issues/3678)

## Summary

A single one-pass audit across `src/dbt/kipptaf/models/marts/**/*.yml` covering
both:

- **Audit 1** — `data_type` drift between mart YAML and BigQuery
  `INFORMATION_SCHEMA.COLUMNS`.
- **Audit 2** — uniqueness / grain test correctness — confirm declared `unique`
  and `dbt_utils.unique_combination_of_columns` tests are on each model's true
  grain, and surface over-specified or missing tests.

Findings are triaged manually; in-PR fixes land alongside the audit script and
report. Hard-to-fix findings get individual follow-up issues.

## Scope

- **In scope:** every model under `src/dbt/kipptaf/models/marts/` (currently ~70
  files across `dimensions/`, `facts/`, `bridges/`).
- **Out of scope:**
  - Productizing the audit script as the reusable
    [#3594](https://github.com/TEAMSchools/teamster/issues/3594) sync tool —
    separate effort.
  - Mart models in other dbt projects (none today).

## Architecture

A single Python script `scripts/audit_marts_yaml.py`, executed from the
devcontainer via `uv run`. Ad-hoc but committed — useful artifact for future
re-runs.

### Audit pass (read-only)

1. Parse each mart YAML; extract per-column `data_type` and declared uniqueness
   test columns (single-column `unique` tests and
   `dbt_utils.unique_combination_of_columns` tests).
2. For each model, query `INFORMATION_SCHEMA.COLUMNS` once per dataset to get
   actual BigQuery column types. Cache per-dataset results in-script.
3. For each YAML-vs-BQ type mismatch, trace upstream lineage via the dbt
   manifest `parent_map` and record every cast/coerce on that column from source
   → mart. The trace informs the right fix; it does not prescribe it.
4. Run grain probes against the materialized table:
   - Confirm declared test columns are unique using
     `count(distinct format("%T|%T|...", col1, col2, ...))` (NULL-safe per
     CLAUDE.md guidance — `concat()` is not).
   - For declared keys with >1 column, drop one column at a time and re-probe;
     flag any subset that is also unique as **over-specified**.
   - For models with no uniqueness test, probe candidate single-column and
     pairwise keys to surface grain candidates.
5. For each declared uniqueness test, fetch the current asset-check status from
   Dagster (`mcp__dagster__get_asset_check_executions`) — last execution outcome
   (PASSED / FAILED / WARN) and timestamp. Record per-model alongside the BQ
   probe result so the two can be compared.
6. Read declared `severity` for each uniqueness test from the YAML. Tests
   configured `severity: warn` mask fan-out by design — surfaced as their own
   finding category.
7. Emit two artifacts:
   - `docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.md` —
     human-readable report.
   - `docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.json` —
     machine-readable companion for diffing future re-runs.

### Fail-hard policy

The audit produces a coherent picture or it aborts. Any of the following raises
and stops the run:

- BigQuery query failure for any model
- YAML parse error in any mart file
- Model not yet materialized (no BQ table)
- Dagster asset-check API failure

Resolve underlying issues (e.g. run a build first) and re-run from scratch.
There is no "skipped" or "errored" bucket in the report.

A currently-failing or warning Dagster test is **not** an audit infrastructure
error — the audit continues and flags it as a finding. Fail-hard is for the
audit's own plumbing, not for the conditions the audit is meant to surface.

### Type bucketing

Findings are bucketed by audit logic, not by fix decision:

- **Pass** — declared test confirmed, no smaller unique subset, no type drift,
  Dagster status PASSED, severity not `warn`.
- **Suspect** — declared test confirmed but a smaller subset is also unique
  (test over-specified), OR multiple plausible grain candidates surfaced.
- **Broken** — declared test fails against live BQ data (silent fan-out present
  today), OR current Dagster status is FAILED.
- **Warn-masked** — uniqueness test declared `severity: warn`. Treated as its
  own finding category regardless of pass/fail status.
- **Status mismatch** — Dagster shows PASSED but the BQ probe finds duplicates
  (or vice versa). Indicates staleness, severity masking, or a probe bug;
  surfaced for human review.
- **Type drift** — orthogonal to grain status; counted per column per model.

## Manual triage pass

After the script run, every finding receives two independent attributes during a
manual review of the report:

### `difficulty`

Captures combined design + code effort, not just LOC:

- **trivial** — mechanical, no judgement. Single YAML edit where the right
  answer is obvious from the BQ probe or upstream trace.
- **moderate** — small judgement call, bounded surface. Adding a missing test
  where the BQ probe found exactly one minimal unique key. One staging-model
  cast change with no downstream renames.
- **hard** — requires design thinking. Examples: grain mismatch with multiple
  plausible unique keys; over-specified test where dropping the surrogate column
  may break consumers; type drift with conflicting upstream casts; finding that
  reveals a deeper modeling question.

Each finding's difficulty entry includes a one-line rationale.

### `disposition`

Independent of difficulty:

- **fix-in-this-pr** — fix lands alongside the audit.
- **defer** — separate follow-up issue; report links the issue number once
  opened.

A trivial finding may still be deferred; a hard finding may still land here. The
two decisions are made per finding during triage.

## Fix pass

For every finding tagged `fix-in-this-pr`:

- Type drift fixes: edit YAML to match BQ, fix the staging cast, or fix at an
  intermediate — whichever the upstream trace makes the obvious right answer.
- Uniqueness test fixes: correct the test columns; add new tests where genuinely
  missing.
- Grain documentation: where the BQ probe confirms the declared test columns are
  the true grain, write a `grain:` line into the YAML description for the model.
  (Models with deferred grain findings stay untouched.)

Validation: `dbt build --select state:modified+` for the modified surface.
Full-refresh where staging casts changed.

For every finding tagged `defer`: open a follow-up issue (one per finding, or
per cluster where multiple findings share a root cause), title
`fix(dbt): <model_name> — <type drift|grain mismatch|both>`, labels `fix` and
`dbt`, body summarizing the report's per-model section. Link back to #3678.

## Report format

`docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.md`:

```markdown
# Mart YAML Audit Report — 2026-05-01

Run: <commit sha> | Models scanned: N | Pass: A | Suspect: B | Broken: C |
Warn-masked: W | Status-mismatch: M | Type drift: D

## Summary table

| Model | Materialization | Contract | Type drift | Grain status | Test severity | Dagster status | BQ probe | Difficulty | Disposition    | Issue |
| ----- | --------------- | -------- | ---------- | ------------ | ------------- | -------------- | -------- | ---------- | -------------- | ----- |
| fct_x | table           | enforced | 0          | pass         | error         | PASSED         | unique   | —          | —              | —     |
| fct_y | table           | enforced | 3          | suspect      | error         | PASSED         | unique   | hard       | defer          | #NNNN |
| fct_z | view            | none     | 0          | broken       | warn          | WARN           | dupes    | moderate   | fix-in-this-pr | —     |

## Per-model details

### fct_y

- Declared grain (from tests): `(student_id, academic_year)`
- Test severity: error
- Dagster current status: PASSED (2026-04-30T03:14:00Z)
- BQ probe: confirmed unique on declared columns
- Smaller-subset probe: `student_id` alone is also unique → over-specified
- Status mismatch: none
- Type drift: 3 columns
  - `created_timestamp`: YAML `timestamp` vs BQ `DATETIME`
    - Upstream trace: `stg_*.created` (datetime) → no further casts
  - ...
- Difficulty: hard — `student_id`-alone uniqueness suggests model may be
  student-grain, not student-year-grain; needs domain review
- Disposition: defer (#NNNN)
```

The JSON companion mirrors the same fields.

## Final PR contents

- `scripts/audit_marts_yaml.py`
- `docs/superpowers/specs/2026-05-01-mart-yaml-audit-design.md` (this file)
- `docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.md`
- `docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.json`
- All `fix-in-this-pr` edits to mart YAMLs, intermediate models, and staging
  models
- Follow-up issue links recorded in the report for every `defer` finding

## Acceptance

- Audit script runs end-to-end without error.
- Report is fully populated — every finding has difficulty + disposition.
- Every `fix-in-this-pr` finding has a corresponding diff in this PR.
- Every `defer` finding has a linked follow-up issue.
- `dbt build` passes on the modified surface.

## Related

- [#3594](https://github.com/TEAMSchools/teamster/issues/3594) — reusable
  BQ-resolution sync tool (separate effort; this audit's script may be partially
  absorbed into it later).
- [#3643](https://github.com/TEAMSchools/teamster/issues/3643) — Task 18
  surfaced the original 11-column type drift on
  `fct_job_candidate_applications`.
- [#3750](https://github.com/TEAMSchools/teamster/issues/3750) — Batch C diamond
  check that motivated Audit 2.
