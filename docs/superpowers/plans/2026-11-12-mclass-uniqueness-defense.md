# mCLASS uniqueness warn-defend-error Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Misfiled Amplify rows warn at staging, get dropped in the kipptaf
mCLASS source intermediates, and error tests prove the drop.

**Architecture:** Each defended model counts rows per collision key with
`count(*) over (partition by ...)` and keeps only rows whose counts are 1. The
partition always includes the per-file columns, so a cross-file double is not
dropped and still fails at error.

**Tech Stack:** dbt (BigQuery), `dbt_utils.unique_combination_of_columns`.

**Spec:**
`docs/superpowers/specs/2026-11-12-mclass-uniqueness-defense-design.md` (read
its _Revision 2026-11-12_ section).

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/fix/claude-mclass-uniqueness-defense`,
  branch `cbini/fix/claude-mclass-uniqueness-defense`. Paths below are relative
  to it.
- Always `uv run dbt`. Invoke the `dbt-local-dev` skill before the first build.
  Dev builds only; no `--target staging` writes.
- Drop ALL colliding rows; never pick one.
- Collision partitions include `_dbt_source_relation` (which file), and also
  `_dbt_source_relation_2` (SFTP vs API) where the model has it.
- The partition uses the raw staging student id, before `focus_student_number`.
- No student ids, names, or row values in commits, the PR, or docs. Use
  `Student A` / `Student B` or counts.
- SQL follows `.claude/rules/dbt-sql.md`. Rationale goes in the properties-yml
  `description:`, not in SQL comments (S18).
- Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Null `device_date` (397 benchmark rows, mostly API). The same-day count must
   not group nulls together:
   `if(device_date is not null, count(*) over (...), 1)`. Task 2's prod check
   pins it: 12 rows dropped, not hundreds.
2. Cross-file doubles: a Paterson row in both the network file and the
   kipppaterson archive must survive the defense and fail the error test. The
   partition must include `_dbt_source_relation`.
3. Aimline drift: the aimline model must drop the same PM rows as the PM
   intermediate. Task 4 compares the counts.
4. `dbt-layer-check` A5: the defense uses a `count(*)` window, not a
   `row_number()` filtered to 1. Run trunk on each SQL file.
5. Downstream fan-out: `int_amplify__benchmark_student_summary` and the mart key
   must be clean after the defense. Task 5 builds the chain.

---

### Task 1: Staging tests to warn

**Files:**

- Modify:
  `src/dbt/amplify/models/mclass/sftp/staging/properties/stg_amplify__mclass__sftp__benchmark_student_summary.yml:12-20`
- Modify:
  `src/dbt/amplify/models/mclass/sftp/staging/properties/stg_amplify__mclass__sftp__pm_student_summary.yml:12-23`

- [ ] **Step 1:** In both files, change the `unique_combination_of_columns`
      `severity: error` to `severity: warn`, and give the test a `description:`.
      The description says that Amplify filed more than one child's results
      under 1 student ID. It says the kipptaf mCLASS intermediate drops the
      colliding rows, so those students show as Not Tested. And it says the fix
      is to have Amplify or the school move the result to the right student in
      mCLASS. Follow the test-description convention in
      `.claude/rules/dbt-yaml.md`.
- [ ] **Step 2:** Run
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <both files> </dev/null`.
      Expected: no issues.
- [ ] **Step 3:** Run `uv run dbt parse --project-dir src/dbt/kippnewark`.
      Expected: it parses clean.
- [ ] **Step 4:** Commit with `fix(dbt): warn on mCLASS staging key collisions`.

### Task 2: Benchmark defense and error proof

**Files:**

- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/int_amplify__mclass__benchmark_student_summary.sql`
- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/properties/int_amplify__mclass__benchmark_student_summary.yml`
- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/properties/int_amplify__mclass__benchmark_student_summary_unpivot.yml:15-22`

**Interfaces:** the output columns are unchanged. No new column survives the
final select.

- [ ] **Step 1: Add the error tests to the properties yml.** Add 2 model-level
      `dbt_utils.unique_combination_of_columns` tests, each with
      `config: severity: error`:
  - `[student_primary_id, school_year, benchmark_period, assessment_grade]`
  - `[student_primary_id, school_year, benchmark_period, device_date]`, with
    `config: where: "device_date is not null"`

  In the unpivot yml, add `config: severity: error` to its existing test.

- [ ] **Step 2: Run the tests against the current SQL to see them fail.** Run
      `uv run dbt build --select int_amplify__mclass__benchmark_student_summary`
      (dev, with the `dbt-local-dev` defer flags). Expected: both new tests
      FAIL, from Student A and Student B.
- [ ] **Step 3: Add the defense.** In `location_xref`, add 2 window columns:
  - `n_grade_collisions`: `count(*)` over
    `_dbt_source_relation, _dbt_source_relation_2, student_primary_id, school_year, benchmark_period, assessment_grade`
  - `n_day_collisions`:
    `if(device_date is not null, count(*) over (<same, with device_date in place of assessment_grade>), 1)`

  Here `student_primary_id` is the raw `ur.` column. In the final select, add
  both columns to `except (...)` and add
  `where n_grade_collisions = 1 and n_day_collisions = 1`. Extend the model
  `description:` with one sentence on the drop rule, why it exists, and that a
  cross-file double is not dropped.

- [ ] **Step 4: Rebuild.** Run the same build. Expected: PASS, and the unpivot
      test passes too:
      `uv run dbt build --select int_amplify__mclass__benchmark_student_summary_unpivot`.
- [ ] **Step 5: Check row counts against prod.** Expected: the dev row count is
      prod's count minus 12. Use BigQuery MCP `count(*)` on the dev relation and
      on `kipptaf_amplify.int_amplify__mclass__benchmark_student_summary`.
- [ ] **Step 6:** Run trunk check on the 3 files. Then commit with
      `fix(dbt): drop colliding mCLASS benchmark rows`.

### Task 3: PM intermediate defense and uniqueness test

**Files:**

- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/int_amplify__mclass__pm_student_summary.sql`
- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/properties/int_amplify__mclass__pm_student_summary.yml`

- [ ] **Step 1: Add the error test.** Add a model-level
      `unique_combination_of_columns` test, `severity: error`, on
      `[student_primary_id, school_year, pm_period, measure, probe_number, device_date, assessment_grade]`.
- [ ] **Step 2: Build to see it fail.** Expected: FAIL, from the Maze duplicate
      on the second Paterson ID.
- [ ] **Step 3: Add the defense.** In `location_xref`, add `n_key_collisions`:
      `count(*)` over
      `_dbt_source_relation, _dbt_source_relation_2, student_primary_id_studentnumber, school_year, pm_period, measure, probe_number, device_date, assessment_grade`.
      Except it in the final select and filter `where n_key_collisions = 1`. Add
      a description sentence, as in Task 2.
- [ ] **Step 4: Rebuild.** Expected: PASS. Record the number of dropped rows
      (prod count minus dev count) for Task 4.
- [ ] **Step 5:** Run trunk check, then commit with
      `fix(dbt): drop colliding mCLASS PM rows`.

### Task 4: Aimline defense

**Files:**

- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/int_amplify__mclass__pm_student_summary_aimline.sql`
- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/properties/int_amplify__mclass__pm_student_summary_aimline.yml`
  (description only; the existing error test stays)

- [ ] **Step 1: Build to see the existing test fail.** Expected: FAIL.
- [ ] **Step 2: Add the defense.** In `base`, add `n_key_collisions`: `count(*)`
      over
      `_dbt_source_relation, student_primary_id_studentnumber, school_year, pm_period, measure, probe_number, device_date, assessment_grade`.
      This staging union has no `_dbt_source_relation_2`. Filter in `combined`
      with `where b.n_key_collisions = 1`. The final `select *` comes from
      `enriched`, so keep the column out of `combined`'s select list. Add a
      description sentence.
- [ ] **Step 3: Rebuild.** Expected: PASS. Expected: prod count minus dev count
      equals Task 3's drop count.
- [ ] **Step 4:** Run trunk check, then commit with
      `fix(dbt): drop colliding mCLASS aimline rows`.

### Task 5: Downstream chain and docs

**Files:**

- Modify: `docs/models/dibels-dashboard-data-model.md` (the _Where the data
  comes from_ table near line 279, and the _Family models_ rows near line 620)
- Modify: `.claude/skills/dibels-dashboard/references/diagnosing.md` (new
  section)

- [ ] **Step 1: Build the downstream chain in dev.** Build
      `int_amplify__benchmark_student_summary`, `int_amplify__all_assessments`,
      `int_assessments__benchmark_scores`, and
      `fct_assessment_scores_enrollment_scoped`, with defer. Expected: every
      uniqueness test passes, including `assessment_score_key` `unique`. If the
      mart build is too costly in dev, run its uniqueness query in BigQuery
      against the dev parents instead, and say so in the PR.
- [ ] **Step 2: Update the reference doc.** State the drop rule where the mCLASS
      intermediates appear. Say it is a data-team defense against Amplify filing
      errors, T&L confirms it, and dropped students show Not Tested until
      Amplify moves the results.
- [ ] **Step 3: Update the skill.** Add a short section to `diagnosing.md`, _A
      student is Not Tested but Amplify shows a score_. Check the mCLASS staging
      warn tests first. A collision there means the intermediate dropped the
      rows on purpose, and the fix is in mCLASS, not the SQL.
- [ ] **Step 4:** Run trunk check on both files, then commit with
      `docs: record the mCLASS collision drop rule`.
