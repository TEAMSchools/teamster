# fct_survey_responses orphan resolution — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive `fct_survey_responses.survey_submission_key` orphans to zero,
surface future terms-sheet gaps as warn-level dbt failures, eliminate latent
NULL-collision in archive fallback hash, and promote the FK relationships test
to `severity: error`.

**Architecture:** Five narrow edits in one PR — NULL-safe
`format('%T_%T_%T', …)` fallback in `historic_archive_submissions`; warn-level
test on `int_surveys__survey_responses` for window-gap rows; warn-level singular
test on `int_surveys__manager_survey_details` for missing admin tuples;
inner-join enforcement of the FK invariant in `fct_survey_responses`; severity
promotion in `fct_survey_responses.yml`.

**Tech Stack:** dbt + BigQuery, dbt_utils, kipptaf project.

**Spec:**
[docs/superpowers/specs/2026-05-28-fct-survey-responses-orphan-resolution-design.md](docs/superpowers/specs/2026-05-28-fct-survey-responses-orphan-resolution-design.md)
(commit `84d5b7553`).

**Issue:** [#4018](https://github.com/TEAMSchools/teamster/issues/4018).

**Worktree:** `.worktrees/cbini/fix/claude-survey-attribution`. All paths in
this plan are relative to that worktree root. All git operations use
`git -C .worktrees/cbini/fix/claude-survey-attribution …` per root CLAUDE.md.

---

## File map

**Modify:**

- `src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql` — replace
  `concat` fallback with `format('%T_%T_%T', …)` (Task 1).
- `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml`
  — add warn-level `expression_is_true` test (Task 3).
- `src/dbt/kipptaf/models/marts/facts/fct_survey_responses.sql` — project
  `survey_submission_key` in `all_responses`; inner-join
  `fct_survey_submissions` in final SELECT (Task 5).
- `src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml` —
  promote `relationships_…__survey_submission_key__…` to `severity: error` (Task
  6).
- `src/dbt/kipptaf/tests/properties.yml` — add description for the new singular
  test (Task 4 sub-step).

**Create:**

- `src/dbt/kipptaf/tests/test_int_surveys__manager_survey_details__terms_coverage.sql`
  — warn-level singular test (Task 4).

**Untouched but referenced:**

- `stg_google_sheets__reporting__terms` (Ops sheet — handed off in PR body).

---

## Task 0: Pre-flight — sync branch with main

**Files:** none modified.

- [ ] **Step 1: Fetch + merge main into the worktree branch**

```bash
git -C .worktrees/cbini/fix/claude-survey-attribution fetch origin main
git -C .worktrees/cbini/fix/claude-survey-attribution merge origin/main
```

Expected: either "Already up to date." or a clean merge with no conflicts. If
conflicts surface, resolve them before continuing — do not push fix commits onto
a stale base.

- [ ] **Step 2: Confirm clean working tree before starting**

```bash
git -C .worktrees/cbini/fix/claude-survey-attribution status --short
```

Expected: empty output. If the YAML modification observed earlier
(`src/dbt/kipptaf/models/marts/facts/properties/fct_survey_submissions.yml`) is
still present uncommitted, ask the user whether to commit, stash, or discard
before continuing.

---

## Task 1: NULL-safe fallback hash in `historic_archive_submissions`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql:213-222`

- [ ] **Step 1: Pre-merge hash-stability check**

Run via BigQuery MCP:

```sql
select count(*) as null_fallback_rows
from `teamster-332318.kipptaf_surveys.int_surveys__manager_survey_details`
where survey_id = 'historic_alchemer_Manager_survey'
  and survey_response_id is null
```

Expected: `null_fallback_rows = 0`. If non-zero, **stop and flag to the user** —
the `concat` → `format` change will produce real hash churn for archive rows,
which per
[src/dbt/kipptaf/models/marts/CLAUDE.md](src/dbt/kipptaf/models/marts/CLAUDE.md)
hash-change discipline requires coordinating with downstream consumers before
merging.

- [ ] **Step 2: Apply the edit**

Replace the `coalesce(... concat(...) ...)` block in
`historic_archive_submissions` (currently lines ~213–222) with:

```sql
            coalesce(
                ms.survey_response_id,
                format(
                    '%T_%T_%T',
                    ms.respondent_df_employee_number,
                    ms.subject_df_employee_number,
                    ms.campaign_reporting_term
                )
            ) as survey_response_id,
```

- [ ] **Step 3: Compile to confirm no syntax error**

```bash
uv run dbt compile \
  --select fct_survey_submissions \
  --project-dir .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf
```

Expected: `Done.` with no errors.

- [ ] **Step 4: Build the model against staging defer**

```bash
uv run dbt build \
  --select fct_survey_submissions \
  --project-dir .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf \
  --defer --state .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf/target/prod/
```

Expected: PASS. Submission count should be unchanged (the fallback path is
unused per Step 1).

- [ ] **Step 5: Commit**

```bash
git -C .worktrees/cbini/fix/claude-survey-attribution add \
  src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql

git -C .worktrees/cbini/fix/claude-survey-attribution commit -m "$(cat <<'EOF'
fix(dbt): null-safe fallback hash in historic_archive_submissions

concat() returns NULL when any argument is NULL, so two archive rows with
NULL respondent or subject employee numbers would both fall back to NULL
and generate_surrogate_key would hash them to the same placeholder.
format('%T_%T_%T', …) emits NULL-distinguishable literals.

Latent today (no archive rows take the fallback path); no observable hash
churn. Refs #4018.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

Expected: pre-commit `trunk fmt` may reformat the SQL; that's fine. Commit
succeeds.

---

## Task 2: Verify orphan reproduction one more time

**Files:** none.

This is a measurement step before adding tests / the inner join, so we can
confirm post-edit row counts.

- [ ] **Step 1: Capture current orphan baseline**

Run via BigQuery MCP:

```sql
select
  count(*) as orphan_rows,
  count(distinct r.survey_submission_key) as distinct_subs
from `teamster-332318.kipptaf_marts.fct_survey_responses` r
left join `teamster-332318.kipptaf_marts.fct_survey_submissions` s
  using (survey_submission_key)
where s.survey_submission_key is null
```

Expected (per spec, as of 2026-05-27): `orphan_rows ≈ 47,788`,
`distinct_subs ≈ 2,727`. Record the exact numbers in the task notes — Task 5's
post-build query should reduce both to 0.

---

## Task 3: Warn-level test for window-gap rows in `int_surveys__survey_responses`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml`

- [ ] **Step 1: Read the current properties yml**

Open the file. Find the model-level `data_tests:` block (it must sit above the
`columns:` block per [src/dbt/CLAUDE.md](src/dbt/CLAUDE.md)). If the block
doesn't exist yet, create it just before `columns:`.

- [ ] **Step 2: Add the warn-level expression_is_true test**

Add the following entry under the model-level `data_tests:`:

```yaml
- dbt_utils.expression_is_true:
    arguments:
      expression: >-
        survey_title not in (
          'School Community Diagnostic Staff Survey',
          'School Community Diagnostic Student Survey',
          'KIPP NJ & KIPP Miami Family Survey',
          'KIPP Miami Re-Commitment Form & Family School Community Diagnostic',
          'Engagement & Support Surveys',
          'Manager Survey'
        ) or (academic_year is not null and term_code is not null)
    config:
      severity: warn
```

Indent to match the surrounding YAML. This test fails for any row whose
`survey_title` requires terms-sheet attribution but whose `academic_year` or
`term_code` resolved to NULL upstream — i.e. submissions that fell outside any
matching SURVEY-type terms window.

- [ ] **Step 3: Parse and run the test in isolation**

```bash
uv run dbt parse \
  --project-dir .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf

uv run dbt test \
  --select 'int_surveys__survey_responses,test_type:generic' \
  --project-dir .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf \
  --defer --state .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf/target/prod/
```

Expected: the new test runs and **warns** (it should fail because 142
submissions are currently window-gap; warn severity keeps CI green). The warn is
the intended signal — it's what Ops will resolve by widening sheet windows.

- [ ] **Step 4: Commit**

```bash
git -C .worktrees/cbini/fix/claude-survey-attribution add \
  src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml

git -C .worktrees/cbini/fix/claude-survey-attribution commit -m "$(cat <<'EOF'
test(dbt): warn on int_surveys__survey_responses window-gap rows

Surfaces submissions that fall outside any matching SURVEY-type terms-sheet
window as a warn-level test at the intermediate layer, instead of bleeding
into the downstream fct_survey_responses FK relationships test where the
mechanism is obscured.

Currently warns on 142 submissions. Refs #4018.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Warn-level singular test for missing admin tuples in `int_surveys__manager_survey_details`

**Files:**

- Create:
  `src/dbt/kipptaf/tests/test_int_surveys__manager_survey_details__terms_coverage.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml`

- [ ] **Step 1: Create the singular test SQL**

Write to
`src/dbt/kipptaf/tests/test_int_surveys__manager_survey_details__terms_coverage.sql`:

```sql
{{ config(severity='warn') }}

select
    ms.campaign_academic_year,
    ms.campaign_reporting_term,
    count(*) as orphan_rows,
from {{ ref("int_surveys__manager_survey_details") }} as ms
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on rt.`name` = 'Manager Survey'
    and ms.campaign_academic_year = rt.academic_year
    and ms.campaign_reporting_term = rt.code
    and rt.type = 'SURVEY'
where ms.campaign_academic_year is not null
  and rt.academic_year is null
group by 1, 2
```

This test returns one row per
`(campaign_academic_year, campaign_reporting_term)` tuple that has no matching
`(name='Manager Survey', type='SURVEY')` row in the terms sheet. Currently warns
on 2,556 archive submissions (Manager AY2022 MGR1 + MGR2).

- [ ] **Step 2: Add the test description to `tests/properties.yml`**

Open `src/dbt/kipptaf/tests/properties.yml`. Find the existing `data_tests:`
list (it starts near the top per the file we read earlier). Add this entry
alphabetically or at the end:

```yaml
- name: test_int_surveys__manager_survey_details__terms_coverage
  description: >-
    Warns when int_surveys__manager_survey_details has a
    (campaign_academic_year, campaign_reporting_term) tuple with no matching
    (name='Manager Survey', type='SURVEY') row in
    stg_google_sheets__reporting__terms. Surfaces Manager Survey admin-tuple
    coverage gaps that would otherwise drop archive rows at the
    fct_survey_submissions terms join.
```

- [ ] **Step 3: Parse and run the test in isolation**

```bash
uv run dbt parse --no-partial-parse \
  --project-dir .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf

uv run dbt test \
  --select test_int_surveys__manager_survey_details__terms_coverage \
  --project-dir .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf \
  --defer --state .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf/target/prod/
```

Expected: **WARN**, with `failures = 2` (one row each for AY2022 MGR1 and MGR2).
`--no-partial-parse` is needed because the description is in a yml that the
partial-parse cache may not pick up immediately (per src/dbt/CLAUDE.md
singular-test description placement note).

- [ ] **Step 4: Commit**

```bash
git -C .worktrees/cbini/fix/claude-survey-attribution add \
  src/dbt/kipptaf/tests/test_int_surveys__manager_survey_details__terms_coverage.sql \
  src/dbt/kipptaf/tests/properties.yml

git -C .worktrees/cbini/fix/claude-survey-attribution commit -m "$(cat <<'EOF'
test(dbt): warn on Manager Survey admin-tuple coverage gaps

Singular test on int_surveys__manager_survey_details that warns when a
(campaign_academic_year, campaign_reporting_term) tuple has no matching
(name='Manager Survey', type='SURVEY') row in
stg_google_sheets__reporting__terms.

Symmetric to the int_surveys__survey_responses window-gap test — covers the
Manager-historic shape where AY/term are valid upstream but the terms sheet
lacks the admin tuple altogether. Currently warns on 2,556 archive
submissions (AY2022 MGR1/MGR2). Refs #4018.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Inner-join FK enforcement in `fct_survey_responses`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_survey_responses.sql`

- [ ] **Step 1: Read the current model**

Re-read `fct_survey_responses.sql` to confirm the structure: two source CTEs
(`general_responses`, `manager_responses`), an `all_responses` UNION ALL, and a
final SELECT that hashes the surrogate keys.

- [ ] **Step 2: Apply the edit**

Rewrite `all_responses` to project `survey_submission_key`, and replace the
final SELECT to inner-join `fct_survey_submissions`:

```sql
    all_responses as (
        select
            survey_id,
            survey_response_id,
            survey_question_id,
            question_shortname,
            response_text,
            response_value,
            {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
                as survey_submission_key,
        from general_responses
        union all
        select
            survey_id,
            survey_response_id,
            survey_question_id,
            question_shortname,
            response_text,
            response_value,
            {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
                as survey_submission_key,
        from manager_responses
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["survey_id", "survey_response_id", "survey_question_id"]
        )
    }} as survey_response_key,

    ar.survey_submission_key,

    {{ dbt_utils.generate_surrogate_key(["question_shortname"]) }}
    as survey_question_key,

    response_value,
    response_text,
from all_responses as ar
inner join {{ ref("fct_survey_submissions") }} as fss
    using (survey_submission_key)
```

Notes:

- `survey_submission_key` is now projected once in the source CTEs rather than
  re-computed in the final SELECT; the hash inputs are identical
  (`survey_id, survey_response_id`) so no hash churn.
- The final SELECT uses table aliasing (`as ar`) per src/dbt/CLAUDE.md ("When a
  SELECT reads from a single table/CTE, do not prefix columns with the alias" —
  here we read from two, so aliasing is correct).
- No `select *` from the join — only the projection columns the final SELECT
  needs.

- [ ] **Step 3: Compile and build**

```bash
uv run dbt build \
  --select fct_survey_responses \
  --project-dir .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf \
  --defer --state .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf/target/prod/
```

Expected: PASS. All tests pass (including the existing `relationships` test,
which still runs at warn for now — gets promoted in Task 6).

- [ ] **Step 4: Confirm row-count delta**

Query the PR-branch schema (per root CLAUDE.md "Pre-merge queries against
PR-branch schema"). After dbt Cloud CI runs, the PR-branch schema follows
`dbt_cloud_pr_<job_definition_id>_<pr_num>_marts`. For local dev verification:

Find your dev marts schema from `src/dbt/kipptaf/profiles.yml` (or
`<repo-root>/.dbt/profiles.yml` for local dev — the schema is typically
`zz_<username>_kipptaf_marts`). Then via BigQuery MCP:

```sql
select
  count(*) as orphan_rows
from `teamster-332318.zz_<username>_kipptaf_marts.fct_survey_responses` r
left join `teamster-332318.zz_<username>_kipptaf_marts.fct_survey_submissions` s
  using (survey_submission_key)
where s.survey_submission_key is null
```

Skip this step if local dev didn't actually build to BigQuery (e.g., `--empty`
runs); the same check happens in CI against the PR-branch schema.

Expected: `orphan_rows = 0`. Row count of `fct_survey_responses` should be
~47,788 lower than the baseline captured in Task 2.

- [ ] **Step 5: Commit**

```bash
git -C .worktrees/cbini/fix/claude-survey-attribution add \
  src/dbt/kipptaf/models/marts/facts/fct_survey_responses.sql

git -C .worktrees/cbini/fix/claude-survey-attribution commit -m "$(cat <<'EOF'
fix(dbt): inner-join fct_survey_submissions in fct_survey_responses

Project survey_submission_key once in all_responses and inner-join the
parent fact in the final SELECT. Encodes the FK invariant the
relationships test asserts, dropping the 47,788 / 2,727 orphan response
rows that have no matching submission.

Once Ops widens the terms sheet (Manager AY2022 MGR1/MGR2 admin rows +
date-window gaps), most of those rows reappear with valid
survey_submission_keys. 28 enrollment-residue rows stay filtered until a
separate follow-up resolves. Refs #4018.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Promote relationships test to `severity: error`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml`

- [ ] **Step 1: Apply the edit**

Find the `survey_submission_key` column's `data_tests:` block (around line ~30
per our earlier read). Add `config: severity: error` to the relationships test:

```yaml
data_tests:
  - relationships:
      arguments:
        to: ref('fct_survey_submissions')
        field: survey_submission_key
      config:
        severity: error
```

No change to `survey_question_key` — its relationships test is already at the
project default (warn for marts per project-level `data_tests:` config); the
spec only calls for promoting the `survey_submission_key` FK because that's the
one Task 5's inner join guarantees to be clean.

- [ ] **Step 2: Run the test against the local build**

```bash
uv run dbt test \
  --select fct_survey_responses \
  --project-dir .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf \
  --defer --state .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf/target/prod/
```

Expected: PASS at error. If FAIL, the inner join from Task 5 isn't dropping all
orphans — re-run Task 5 Step 4 to investigate.

- [ ] **Step 3: Commit**

```bash
git -C .worktrees/cbini/fix/claude-survey-attribution add \
  src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml

git -C .worktrees/cbini/fix/claude-survey-attribution commit -m "$(cat <<'EOF'
test(dbt): promote fct_survey_responses.survey_submission_key FK to error

The inner join added in fct_survey_responses now guarantees zero orphans
against fct_survey_submissions, so the relationships test can run at error.
Future Ops-sheet drift surfaces at the two new warn-level intermediate
tests instead of at this downstream FK check. Refs #4018.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Full subgraph build + commit verification

**Files:** none modified.

- [ ] **Step 1: Build the full surveys subgraph locally**

```bash
uv run dbt build \
  --select int_surveys__survey_responses+ int_surveys__manager_survey_details fct_survey_submissions+ fct_survey_responses+ \
  --project-dir .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf \
  --defer --state .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf/target/prod/
```

Expected: all models PASS. The new warn-level tests from Tasks 3 and 4 surface
as warnings (142 + 2,556 submissions affected). The promoted
`relationships_…__survey_submission_key__…` PASSES at error.

- [ ] **Step 2: Verify the commit log**

```bash
git -C .worktrees/cbini/fix/claude-survey-attribution log --oneline origin/main..HEAD
```

Expected: four `fix(dbt)` / `test(dbt)` commits on top of the spec commit
(`84d5b7553`) — one per Task 1, 3, 4, 5, 6. (Task 0 and Task 7 don't produce
commits; Task 2 captures a baseline but doesn't modify files.)

- [ ] **Step 3: Run trunk check to catch lint issues that pre-commit hook
      didn't**

```bash
.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql \
  src/dbt/kipptaf/models/marts/facts/fct_survey_responses.sql \
  src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml \
  src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml \
  src/dbt/kipptaf/tests/test_int_surveys__manager_survey_details__terms_coverage.sql \
  src/dbt/kipptaf/tests/properties.yml
```

Run from inside the worktree
(`cd .worktrees/cbini/fix/claude-survey-attribution`) — per root CLAUDE.md,
`trunk check --force <abs-worktree-paths>` from the main repo silently returns
"no applicable linters".

Expected: clean. Address any sqlfluff / yamllint findings before pushing.

---

## Task 8: File follow-up issue for enrollment-residue rows

**Files:** none in repo; opens a GitHub issue.

- [ ] **Step 1: Create the issue**

Use `mcp__github__issue_write` with:

- title:
  `fix(dbt): fct_survey_responses Student SCD enrollment-attribution residue (28 submissions)`
- body: short summary (per spec): 28 Student SCD orphan submissions whose
  `respondent_email` doesn't resolve to an `int_extracts__student_enrollments`
  row overlapping `date_submitted`. 19 emails with no enrollment ever; 9 with
  enrollment but date-miss. Filtered out at build time by the inner join added
  in #4018; tracked separately because no clean upstream fix exists. Link to
  #4018.
- labels: `fix`, `dbt`

- [ ] **Step 2: Record the new issue number**

Capture the returned issue number; reference it in the PR body's "Known
deferred" section in Task 9.

---

## Task 9: Open the PR

**Files:** PR body only.

- [ ] **Step 1: Push the branch**

```bash
git -C .worktrees/cbini/fix/claude-survey-attribution push
```

Expected: dbt Cloud CI fires automatically.

- [ ] **Step 2: Wait for dbt Cloud CI to reach terminal state**

Do not open the PR with code changes still in-flight (root CLAUDE.md: pushing
cancels in-progress runs; bundle fixes into one push). After the push from Step
1, monitor via:

```python
# Via mcp__dbt__list_jobs_runs and mcp__dbt__get_job_run_details
```

- [ ] **Step 3: Verify CI warnings match expectations**

After CI passes:

```python
# mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)
```

Expected warnings:

- `dbt_utils_expression_is_true_int_surveys__survey_responses_…` — 142
  window-gap submissions.
- `test_int_surveys__manager_survey_details__terms_coverage` — 2 rows (AY2022
  MGR1 + MGR2).

Any other new warning is unexpected — investigate before opening the PR.

- [ ] **Step 4: Create the PR**

Use `mcp__github__create_pull_request` with the body following
[`.github/pull_request_template.md`](.github/pull_request_template.md). Key
sections to fill:

- **Summary** — bullets covering the 5 edits.
- **Action required from Ops** (called out explicitly):
  - Add
    `(name='Manager Survey', academic_year=2022, code='MGR1', type='SURVEY', start_date=…, end_date=…)`
    and `(… code='MGR2' …)` rows to `stg_google_sheets__reporting__terms`.
    Reclaims 2,556 submissions.
  - Widen Student SCD AY2025 window (currently 2025-12-01 → 2026-03-01) or add
    interim windows for off-period submissions. Reclaims 114.
  - Add Staff SCD coverage for 2024-11-09 → 2025-02-13. Reclaims 19.
  - Widen Manager Survey AY2024 MGR1/MGR2 windows to cover 2024-11-09 →
    2025-04-26 stragglers. Reclaims 9.
  - These edits clear the two new warn-level tests.
- **Known deferred** — 28 Student SCD enrollment-residue rows filtered at build
  time; tracked in the new issue from Task 8.
- **Refs / Closes** — `Refs #4018`. (Don't `Closes` until orphans actually hit
  zero in prod after Ops edits land.)

---

## Acceptance gates (per spec)

|   # | Gate                                                       | Verified in                              |
| --: | ---------------------------------------------------------- | ---------------------------------------- |
|   1 | NULL-safe fallback hash                                    | Task 1                                   |
|   2 | Window-gap warn test                                       | Task 3                                   |
|   3 | Admin-tuple-coverage warn test                             | Task 4                                   |
|   4 | Inner-join FK enforcement                                  | Task 5                                   |
|   5 | Severity promotion to error                                | Task 6                                   |
|   6 | Pre-merge hash-stability check (`null_fallback_rows = 0`)  | Task 1, Step 1                           |
|   7 | dbt Cloud CI passes at error; new warns match expectations | Task 9, Step 3                           |
|   8 | Post-merge orphan count = 0                                | Verify in prod after merge (out of plan) |

---

## Notes for the implementer

- Every git operation uses
  `git -C .worktrees/cbini/fix/claude-survey-attribution`. Bare `git` from the
  main repo silently commits to `main`.
- Every dbt operation uses
  `--project-dir .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf`.
  Do NOT use `uv --directory <worktree> run dbt` — that overrides cwd to the
  worktree root where `dbt_project.yml` doesn't exist.
- `dbt build --defer --state` paths are relative to `--project-dir`. The prod
  manifest path `src/dbt/kipptaf/target/prod/` is refreshed by
  `.git/hooks/post-merge` on git pull.
- Pre-commit `trunk fmt` runs automatically; pre-push `trunk check` enforces
  sqlfluff + yamllint. If a commit message gets blocked by the hook, fall back
  to `.claude/scratch/commit-msg.txt` per .claude/CLAUDE.md.
- Do not push fix commits onto an in-progress dbt Cloud CI run — wait for
  terminal state first.
