# Survey-fact submission grain — mart-level unification

## Tracking

- Primary: [#3899](https://github.com/TEAMSchools/teamster/issues/3899) — remove
  `select distinct` from eight survey-fact / admin-dim CTEs
- Also closes: [#3896](https://github.com/TEAMSchools/teamster/issues/3896) —
  Manager Survey `survey_submission_key` hash mismatch
- Follow-up tracker:
  [#3918](https://github.com/TEAMSchools/teamster/issues/3918) — extract
  `int_surveys__survey_submissions`

## Problem

Two mart models carry the submission-grain collapse for survey data:

- [`fct_survey_submissions`](../../../src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql)
  — four legs (staff / student / family Google Forms / Manager)
- [`dim_survey_administrations`](../../../src/dbt/kipptaf/models/marts/dimensions/dim_survey_administrations.sql)
  — three legs plus a final `deduped` collapse

Each leg uses `select distinct` to collapse question-grain rows from
`int_surveys__survey_responses` (or `int_surveys__manager_survey_details`) down
to one row per submission. Each carries a stale `-- TODO: #3629 / #3635` comment
pointing at closed issues.

Empirical sizing on prod 2026-05-12 confirmed the dedup is a pure
projection-identity collapse (274,820 → 27,482 in the student leg = 10×
question-grain fan-out, zero enrollment fan-out). The grain mismatch is not a
data-quality dedup — it's a source-grain / consumer-grain mismatch.

Additionally, Manager Survey rows hash divergently between
`fct_survey_responses` (sources `int_surveys__survey_responses` Google Forms
branch) and `fct_survey_submissions.manager_submissions` (sources
`int_surveys__manager_survey_details`), producing ~100 FK orphans on prod.

## Out of scope

Extracting a true `int_surveys__survey_submissions` intermediate is the right
long-term fix and is tracked in #3918. This spec covers the mart-level fix only
— it ships the hash unification and removes the `select distinct` pattern
without adding new intermediates, on the explicit understanding that the
structural refactor will follow.

## Design

### Submission-grain CTE pattern

Inside each mart, add a `submissions_grain` CTE using `dbt_utils.deduplicate()`:

```sql
submissions_grain as (
    {{
        dbt_utils.deduplicate(
            relation=ref("int_surveys__survey_responses"),
            partition_by="survey_id, survey_response_id",
            order_by="survey_question_id",
        )
    }}
)
```

This is the project-blessed pattern (root CLAUDE.md → "No manual
deduplication"). The columns the marts project don't vary across questions of a
submission, so `order_by` choice does not affect correctness — a header comment
notes this.

### `fct_survey_submissions` — four-leg restructure

All four legs source respondent identity, dates, AY/term, and hash inputs from
`submissions_grain`. Per-leg differences:

- **Staff / Student / Family Google Forms** — filter `submissions_grain` to the
  leg's respondent-type predicate (today inferred from `survey_title`). Existing
  per-leg join logic (student enrollment lookup, etc.) hangs off
  `submissions_grain` instead of the raw responses table.
- **Manager** — filter `submissions_grain` to the Manager form_id.
  Subject-of-evaluation columns (`subject_employee_number`, subject staff
  details) come from a
  `left join {{ ref("int_surveys__manager_survey_details") }}` on
  `(survey_id, survey_response_id)`, used **only** for the overlay — hash inputs
  stay on `submissions_grain`.
- **Historic Alchemer Manager archive** — isolated union arm sourced from
  `int_surveys__manager_survey_details` filtered to
  `survey_id = 'historic_alchemer_Manager_survey'`. These rows have
  `survey_response_id IS NULL` and use the deterministic fallback hash
  `coalesce(survey_response_id, concat(respondent_emp, '_', subject_emp, '_', term))`.
  They don't appear in `fct_survey_responses`, so they create no FK orphans by
  definition.

### `dim_survey_administrations` — three-leg restructure

Same `submissions_grain` CTE pattern. The three admin-grain CTEs (staff /
student / Manager) replace `select distinct` with the deduped CTE projection.
The trailing `deduped` CTE on the union also switches from `select distinct` to
`dbt_utils.deduplicate()` on the admin grain.

### Hash unification

After the restructure, both facts compute `survey_submission_key` from the same
source row identity:

- `fct_survey_responses.survey_submission_key` — already hashes
  `[survey_id, survey_response_id]` from `int_surveys__survey_responses`
  (unchanged)
- `fct_survey_submissions.survey_submission_key` — same hash inputs, now from
  the same source row

Manager rows hash identically because they flow through `submissions_grain`
(`int_surveys__survey_responses` Google Forms branch) in both facts. Closes
#3896.

### TODO comment update

Replace `-- TODO: #3629 / #3635 — upstream at response grain` with
`-- TODO: #3918 — extract int_surveys__survey_submissions intermediate` at each
`submissions_grain` site.

### `int_surveys__manager_survey_details` header comment

Add a header comment to the intermediate noting that Manager respondent identity
should be sourced from `int_surveys__survey_responses` going forward; this model
is retained for the subject-of-evaluation overlay and the historic Alchemer
archive only. Removal tracked in #3918.

## Risks

- **Deduplicate `order_by` choice.** `survey_question_id` works on Google Forms;
  on Alchemer it's `safe_cast(string)` but values exist. Since projected columns
  don't vary across questions of a submission, choice does not affect
  correctness. Captured in inline comment.
- **Manager subject overlay miss.** If a Manager row exists in
  `submissions_grain` but not in `int_surveys__manager_survey_details` (because
  of LDAP join failures in the latter), the subject columns are null. Acceptable
  — those rows currently don't surface in `fct_survey_submissions` at all, so
  the new behavior strictly expands coverage. Verify residual orphan count
  post-merge.
- **`int_surveys__manager_survey_details` deduped_ri filter.** The
  intermediate's
  `row_number() over (partition by survey_id, year, term, respondent_emp, subject_emp) = 1`
  filter currently keeps one response per (respondent, subject, term). After the
  restructure, the Manager leg's `submissions_grain` carries every response; the
  subject overlay's `row_number` filter may double-resolve on duplicate
  responses. Spec phase verifies whether this introduces fan-out at the mart
  join site; if so, the subject overlay must apply `row_number = 1` keyed on
  `(survey_id, survey_response_id)` instead.

## Acceptance

- [ ] All four CTEs in `fct_survey_submissions` source from `submissions_grain`
      via `dbt_utils.deduplicate()` — no `select distinct`
- [ ] All three (+ trailing `deduped`) CTEs in `dim_survey_administrations`
      source from `submissions_grain` — no `select distinct`
- [ ] Manager subject overlay joins `int_surveys__manager_survey_details` only
      for subject columns; hash inputs come from `submissions_grain`
- [ ] Historic Alchemer Manager archive isolated as its own union arm in
      `fct_survey_submissions`
- [ ] `survey_submission_key` uniqueness test passes on both facts
- [ ] `dim_survey_administrations` PK uniqueness test passes
- [ ] `fct_survey_responses.survey_submission_key → fct_survey_submissions.survey_submission_key`
      relationships test returns 0 orphans (promote from WARN to error in this
      PR)
- [ ] Stale TODO refs (#3629, #3635) replaced with #3918
- [ ] `int_surveys__manager_survey_details` carries header comment noting its
      narrowed role

## Verification commands

```bash
uv run dbt build \
  --select fct_survey_submissions+ fct_survey_responses+ dim_survey_administrations+ \
  --project-dir src/dbt/kipptaf
```

Pre-merge orphan check against PR-branch schema (see root CLAUDE.md → BigQuery
MCP for `dbt_cloud_pr_*` resolution).
