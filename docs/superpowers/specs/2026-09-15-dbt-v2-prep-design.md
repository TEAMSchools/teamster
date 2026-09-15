# Prepare the repo for dbt v2 ahead of BigQuery GA

Design for [#5319](https://github.com/TEAMSchools/teamster/issues/5319).

## Problem

dbt v2 shipped on 2026-09-14. It is the Rust engine formerly called Fusion,
published on PyPI as `dbt` and replacing `dbt-core` plus `dbt-bigquery`. The
BigQuery adapter is Preview, not GA, so production stays on dbt 1.12.

The repo is closer to ready than expected. Verified on 2026-09-14 with the real
2.0.0 binary via `uv run --with dbt==2.0.0`:

| Check                                             | Result                                       |
| ------------------------------------------------- | -------------------------------------------- |
| `dbt parse`, all 5 runnable `kipp*` projects      | Clean. `kipppaterson` emits 1 warning.       |
| `dbt compile --target dev`, `kipptaf`             | 1818 of 1818 nodes succeed, 14 warnings.     |
| `dbt debug` with `method: oauth`                  | Connects to BigQuery.                        |
| `config.get` on meta, YAML anchors, custom mats   | None in the repo.                            |
| Removed CLI flags (`--models`, `--resource-type`) | 1 hit in `scripts/dbt-yaml.py`.              |
| `require-dbt-version: <2.0.0` in 10 packages      | Did not block 2.0.0 parse. Widen regardless. |

What remains is small, and nothing checks that it stays that way. Without a
gate, 1442 `kipptaf` models drift for months and the flip becomes a bug hunt.

## Decision

Prep now; flip at BigQuery GA. Two pull requests off this branch:

1. Pins, script, and a CI parse gate.
2. Rewrite the 14 models dbt's static SQL analyzer cannot read.

Developers, Dagster, and dbt Platform stay on 1.12 until GA. See _Out of scope_.

## Design

### PR 1: pins, script, gate

**Pins.** `require-dbt-version` becomes `[">=1.12.0", "<3.0.0"]` in the 10
source-system `dbt_project.yml` files that carry the key today: `cambium`,
`deanslist`, `edplan`, `focus`, `iready`, `overgrad`, `pearson`, `powerschool`,
`renlearn`, `titan`. `amplify` and `finalsite` have no pin and stay as they are.
Real 2.0.0 does not enforce the old pin, but the dbt Platform readiness panel
and the package hub read it, and widening is the documented contract.

**Script.** [scripts/dbt-yaml.py](../../../scripts/dbt-yaml.py) line 37:
`--resource-type=model` becomes `--resource-types=model`. dbt 1.12 accepts both
spellings; 2.0.0 accepts only the plural.

**Gate.** New workflow `.github/workflows/dbt-v2-parse.yaml`.

- Trigger: `pull_request` with `paths: [src/dbt/**]`. Gate on
  `github.actor != 'dependabot[bot]'` like the other workflows.
- One job, matrix over `kipptaf`, `kippnewark`, `kippcamden`, `kippmiami`,
  `kipppaterson`.
- Steps: `actions/checkout` (same pinned version as the other workflows),
  `astral-sh/setup-uv` pinned to a 40-char SHA, then in
  `src/dbt/${{ matrix.project }}`:

  ```bash
  uv run --with dbt==2.0.0 dbt deps
  uv run --with dbt==2.0.0 dbt parse --target defer
  ```

  with `DBT_PROFILES_DIR` set to the project directory so the shipped
  `profiles.yml` is used.

- No credentials. Verified: parse succeeds with gcloud config hidden and the
  shipped profile.
- Warning-tolerant. 2.0.0 has no `--warn-error`, and the `kipppaterson` warning
  (below) is an upstream false positive.
- The pin `dbt==2.0.0` is deliberate. The gate tests the binary we will ship,
  not the 1.12 `--use-v2-parser` delegate, which runs rc.2 and skips
  `require-dbt-version` and package resolution.

### PR 2: the 14-model rewrite

All 14 warnings are `SyntaxInvalid (dbt0101)` from dbt's own SQL parser, which
v2 runs over compiled SQL for column-level lineage, `dbt lint`, and parse-time
semantic errors. BigQuery runs the SQL fine; v2 tooling goes blind on these
models. `.claude/rules/dbt-sql.md` already rules against the first idiom.

**Union sites**, all under `src/dbt/kipptaf/models/students/intermediate/`:

| Model                                        | Form                           |
| -------------------------------------------- | ------------------------------ |
| `int_students__attendance_daily`             | `full union all corresponding` |
| `int_students__category_grades`              | `full union all corresponding` |
| `int_students__course_enrollments`           | `full union all corresponding` |
| `int_students__course_sections`              | `full union all corresponding` |
| `int_students__courses`                      | `full union all corresponding` |
| `int_students__final_grades`                 | `full union all corresponding` |
| `int_students__gpa`                          | `full union all corresponding` |
| `int_students__gradebook_assignments_scores` | `full union all corresponding` |
| `int_students__graduation_pathway_scores`    | `union all corresponding`      |
| `int_students__student_enrollments`          | `union all corresponding`      |

Each becomes a positional `union all` with both branches enumerated in the same
order and `cast(null as <type>)` padding for columns one side lacks.
`attendance_daily` and `course_enrollments` union a `select *` branch today and
need the full column list written out. Delete the inline comments that defend
`corresponding` (`attendance_daily` lines 76 and 141,
`graduation_pathway_scores` line 175, `student_enrollments` line 293) and update
the `properties.yml` note on `course_enrollments` line 45 about column pruning.

**String-continuation sites.** BigQuery concatenates adjacent string literals;
the analyzer does not. Four models spell one survey title across two literals:
`bridge_survey_expectations` (line 116), `fct_survey_responses` (line 20),
`fct_survey_submissions` (line 141), `dim_surveys` (line 82, which also carries
a `trunk-ignore(sqlfluff/RF05)` to drop). Each becomes a single literal, or `||`
if the line would exceed sqlfluff's 88-column limit.

### The `kipppaterson` warning: root cause, no change

`UnusedResourceConfigPath (dbt1097)` lists 8 `+enabled: false` paths under
`models.powerschool.sis.staging.dlt` as matching nothing. They do match. The
2.0.0 manifest shows every listed `dlt` variant in `disabled`, identical to
1.12, and `dbt ls` under 2.0.0 returns none of them.

Cause: each listed model exists in 2 or 3 same-named variants (`odbc`, `sftp`,
`dlt`) that share one unique id, `model.powerschool.<name>`. v2 tracks
config-path usage by that id, so a sibling variant's record shadows the `dlt`
path. Proof: the single-variant `int_powerschool__gpnode: +enabled: false` two
lines up in the same file does not warn. Cosmetic. File upstream on
`dbt-labs/dbt`; the gate tolerates it.

## Out of scope

- Moving developers, the Dagster image, or dbt Platform environments to v2
  before BigQuery GA. `dagster-dbt` auto-detects the installed engine with no
  per-resource switch, dbt's install guidance is one engine per machine, and
  branch deployments write real datasets.
- Deleting the archived `odbc` and `sftp` staging variants to remove the
  duplicate-name condition. `kippmiami` archive rebuilds still use `odbc`.
- Any `compile` gate. The analyzer warnings surface only at `compile`, which
  needs BigQuery credentials and introspection reads on every PR. The one-time
  rewrite plus the existing SQL rule carry this.

## Flip-day runbook

Not part of this issue. Gated on the BigQuery adapter reaching GA.

1. `pyproject.toml`: replace `dbt-core` and `dbt-bigquery` with `dbt>=2,<3`;
   `uv lock`.
2. Confirm `dagster-dbt project prepare-and-package` in the Dockerfile builds
   with the 2.0.0 binary. `dagster-dbt` supports the engine from 1.11.5.
3. Verify on the v2 BigQuery adapter: `job_retries: 3`,
   `job_execution_timeout_seconds: 900`, and `threads: 40` (v2 treats it as a
   cap). Both keys parse today; whether they act is unverified.
4. Confirm `dbt ls --select stg_powerschool__gpnode` in `kipppaterson` still
   returns nothing.
5. Move the `kipptaf` dbt Platform environment (project 211862) to the v2
   release track. Enable the readiness panel first (Account settings, Account).
6. Bump the gate's `dbt==` pin to the shipped version, or drop `--with` once
   `dbt` is the project dependency.

## Testing

- PR 1: the gate itself. Green on all 5 projects on the PR that adds it.
- PR 2: `uv run --with dbt==2.0.0 dbt compile --target dev` in `kipptaf` returns
  0 warnings. `dbt build --select <14 models> --target dev --defer` and row
  counts match pre-change for each model. A positional union is where column
  swaps hide, so also diff one row per model against prod on a fixed key.
