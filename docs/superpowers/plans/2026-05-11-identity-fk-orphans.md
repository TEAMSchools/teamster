# Identity FK orphans implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close [#3863](https://github.com/TEAMSchools/teamster/issues/3863) and
resolve the FLEID/DeansList portions of
[#3647](https://github.com/TEAMSchools/teamster/issues/3647) by fixing
cross-system identity FK orphans with direct/natural joins; deliver a
SmartRecruiters feasibility audit doc to close
[#3647](https://github.com/TEAMSchools/teamster/issues/3647) and defer the SR
build.

**Architecture:** Audit before model — each identity gap is paired with a
BigQuery probe that confirms (or refutes) a direct-key join before any model
change. Fixes land in existing intermediate / mart models, not new crosswalk
models. SmartRecruiters is audit-only in this batch.

**Tech Stack:** dbt (BigQuery), `uv run dbt`, dbt Cloud CI, `cube`/`bigquery`
MCP for read-only probes.

**Branch:** `cbini/fix/claude-identity-fk-orphans` (worktree at
`.worktrees/cbini/fix/claude-identity-fk-orphans`). Run all `git` and
`uv run dbt` commands with `-C <worktree>` / `--project-dir <worktree>/...`.

**Reference docs:** Read before starting work in each area —
[src/dbt/CLAUDE.md](src/dbt/CLAUDE.md),
[src/dbt/kipptaf/CLAUDE.md](src/dbt/kipptaf/CLAUDE.md),
[src/dbt/kipptaf/models/marts/CLAUDE.md](src/dbt/kipptaf/models/marts/CLAUDE.md).

---

## PR 1 — Direct-key fixes (FLEID, DeansList, Paterson 8)

### Task 1: FLEID — audit + fix

**Files:**

- Probe: ad-hoc BigQuery via `mcp__bigquery__execute_sql`
- Modify:
  `.worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kippmiami/models/fldoe/intermediate/int_fldoe__all_assessments.sql`
- Modify (if needed):
  `.worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kipptaf/models/fldoe/intermediate/int_fldoe__all_assessments.sql`
- YAML: corresponding `*/properties/int_fldoe__all_assessments.yml` files for
  any new column descriptions.

#### Step 1.1: Read prerequisite docs

Read [src/dbt/CLAUDE.md](src/dbt/CLAUDE.md) and
[src/dbt/kipptaf/models/marts/CLAUDE.md](src/dbt/kipptaf/models/marts/CLAUDE.md)
in full before touching SQL. Confirm understanding of the column-naming rubric
and strict-chain traversal.

- [ ] Docs read.

#### Step 1.2: Audit — does PowerSchool carry FLEID on `students`?

Run via `mcp__bigquery__execute_sql` against `teamster-332318`:

```sql
select
  count(*) as n_students,
  countif(state_studentnumber is not null) as n_with_state_id,
  countif(state_studentnumber is not null and regexp_contains(state_studentnumber, r'^\d{14}$')) as n_fleid_shaped
from `teamster-332318`.kippmiami_powerschool.students;
```

Expected if the FLEID hypothesis holds: `n_with_state_id ≈ n_students` for Miami
students, with most values matching the 14-digit FLEID pattern.

- [ ] Probe run. Record `n_students`, `n_with_state_id`, `n_fleid_shaped` in a
      scratch note (`.claude/scratch/fleid-audit.md`). Do NOT paste raw rows or
      names into the PR — aggregates only.

#### Step 1.3: Audit — does FLDOE's FLEID match PowerSchool's `state_studentnumber`?

```sql
with fldoe as (
  select distinct cast(state_student_id as string) as fleid
  from `teamster-332318`.kippmiami_dbt.int_fldoe__all_assessments
  where state_student_id is not null
),
ps as (
  select distinct state_studentnumber as fleid, student_number
  from `teamster-332318`.kippmiami_powerschool.students
  where state_studentnumber is not null
)
select
  count(*) as n_fldoe_distinct,
  countif(ps.student_number is not null) as n_matched,
  countif(ps.student_number is null) as n_unmatched
from fldoe
left join ps using (fleid);
```

- [ ] Probe run. Record match rate in scratch note.

#### Step 1.4: Decision point

- If match rate > 99%, proceed to Step 1.5 (direct-key fix).
- If match rate is 90–99%, document residual unmatched FLEIDs (counts only) in
  scratch note and proceed; expect a small residual in verification at Step 1.7.
- If match rate < 90%, STOP — the hypothesis is wrong. Re-open the spec with the
  user; the FLEID gap may need a real crosswalk model or alternate join key.

- [ ] Decision recorded.

#### Step 1.5: Modify `int_fldoe__all_assessments` to resolve to `student_number`

Open
[.worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kippmiami/models/fldoe/intermediate/int_fldoe\_\_all_assessments.sql](.worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kippmiami/models/fldoe/intermediate/int_fldoe__all_assessments.sql).
Identify where the model currently produces `student_number` (or fails to). Add
a left join to `{{ ref('stg_powerschool__students') }}` (or the equivalent
canonical student source per
[src/dbt/kippmiami/CLAUDE.md](src/dbt/kippmiami/CLAUDE.md)) on
`state_student_id = state_studentnumber`, and project `student_number` from
PowerSchool. Preserve the FLEID column for downstream use.

Mirror the change in the `kipptaf` copy if both projects model FLDOE
assessments. Confirm the downstream `fct_assessment_scores_enrollment_scoped`
derives `student_key` from `student_number` (the spec assumption); if it derives
from a different input, adjust accordingly.

- [ ] Diff produced. Both project copies aligned if applicable.

#### Step 1.6: Build the model and downstream

```bash
uv run dbt build \
  --project-dir .worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kippmiami \
  --select int_fldoe__all_assessments+
```

```bash
uv run dbt build \
  --project-dir .worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kipptaf \
  --select fct_assessment_scores_enrollment_scoped
```

Expected: PASS, with any pre-existing warnings unchanged (no new warnings).

- [ ] Builds green locally.

#### Step 1.7: Verify against #3863 reproduce query

Run #3863's reproduce query against the PR-branch CI schema
(`dbt_cloud_pr_<ci_id>_<pr_num>_<schema>`) once CI seeds it; until then,
substitute the local target schema:

```sql
select da.test_type, da.region, count(*) as n_orphans
from `<schema>`.fct_assessment_scores_enrollment_scoped as f
left join `<schema>`.dim_students as d using (student_key)
left join `<schema>`.dim_assessment_administrations as da using (assessment_administration_key)
where f.student_key is not null and d.student_key is null
group by 1, 2 order by n_orphans desc;
```

Expected: 0 Miami rows. Paterson 8 rows still present (Task 3 closes them).

- [ ] Probe shows 0 Miami orphans.

#### Step 1.8: Commit

```bash
git -C .worktrees/cbini/fix/claude-identity-fk-orphans add \
  src/dbt/kippmiami/models/fldoe/intermediate/int_fldoe__all_assessments.sql \
  src/dbt/kippmiami/models/fldoe/intermediate/properties/int_fldoe__all_assessments.yml \
  src/dbt/kipptaf/models/fldoe/intermediate/int_fldoe__all_assessments.sql \
  src/dbt/kipptaf/models/fldoe/intermediate/properties/int_fldoe__all_assessments.yml

git -C .worktrees/cbini/fix/claude-identity-fk-orphans commit -m \
  "fix(dbt): resolve FLEID rows to student_number via PowerSchool state_studentnumber

Closes Miami bucket in #3863. Refs #3647."
```

Drop any file from the `add` list that wasn't actually modified.

- [ ] Committed.

---

### Task 2: DeansList — audit + fix

**Files:**

- Probe: ad-hoc BigQuery
- Read:
  `.worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/deanslist/models/staging/stg_deanslist__users.sql`
- Modify (likely):
  `.worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kipptaf/models/marts/facts/fct_behavioral_incidents.sql`
- Modify:
  `.worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kipptaf/models/marts/facts/properties/fct_behavioral_incidents.yml`
  (add `relationships` test on new FK)

#### Step 2.1: Audit — does DeansList carry an email field on users?

Inspect the columns on `stg_deanslist__users` and the raw source it pulls from.
Run:

```sql
select column_name, data_type
from `teamster-332318`.deanslist_dbt.INFORMATION_SCHEMA.COLUMNS
where table_name = 'stg_deanslist__users'
order by ordinal_position;
```

- [ ] Column list captured. Identify the email-bearing column (likely `email`,
      `email_address`, or similar).

#### Step 2.2: Audit — what is the email match rate to `int_people__staff_roster`?

```sql
with dl as (
  select distinct lower(<email_col>) as email, user_id
  from `teamster-332318`.deanslist_dbt.stg_deanslist__users
  where <email_col> is not null
),
staff as (
  select distinct lower(google_email) as email, employee_number
  from `teamster-332318`.kipptaf_dbt.int_people__staff_roster
  where google_email is not null
)
select
  count(*) as n_dl_users,
  countif(staff.employee_number is not null) as n_matched
from dl
left join staff using (email);
```

Substitute `<email_col>` with the column identified in Step 2.1, and swap
`google_email` for whatever `int_people__staff_roster` exposes if different.

- [ ] Match rate recorded in `.claude/scratch/deanslist-email-audit.md`.
      Decision: if match rate is high (>95%), proceed with direct email join and
      NULL FK for unmatched. If significantly lower, pause and re-discuss with
      user before continuing.

#### Step 2.3: Inspect current `fct_behavioral_incidents` shape

Open the file. Identify how DL incidents currently flow in and the place where
`staff_key` would attach (likely a `left join` against a staff dimension keyed
on `employee_number`). Confirm there's no existing `staff_key` column. Note the
existing dim it should FK into (the spec references
`dim_staff_work_assignments`; verify against the marts CLAUDE.md naming).

- [ ] Current shape understood. Confirmed target dim.

#### Step 2.4: Write the failing `relationships` test first

In
[.worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kipptaf/models/marts/facts/properties/fct_behavioral_incidents.yml](.worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kipptaf/models/marts/facts/properties/fct_behavioral_incidents.yml),
add a `staff_key` column entry with a `relationships` test against the target
staff dim:

```yaml
- name: staff_key
  description: FK to the referring staff member from DeansList create_by.
  data_tests:
    - relationships:
        to: ref('dim_staff_work_assignments') # adjust per Step 2.3
        field: staff_key
        config:
          where: staff_key is not null
          severity: warn # match surrounding FK tests; promote to error if convention is error
```

Match the `severity` and `where` shape used by other FK tests in the same file.

- [ ] Test entry added (model still lacks the column, so test will
      "pass-with-zero-rows" until the column exists).

#### Step 2.5: Add `staff_key` to `fct_behavioral_incidents`

Modify the SQL to:

1. Project lowercased DL `create_by_email` (or whatever column the audit
   identified — name the projected CTE column descriptively per the marts
   rubric).
2. Left join to the staff source (likely `ref('int_people__staff_roster')`) on
   email to resolve `employee_number`.
3. Derive `staff_key` from `employee_number` matching the existing `staff_key`
   hashing convention in the marts layer (check sibling facts; do not invent a
   new scheme).

Stage the change so each step compiles cleanly.

- [ ] SQL change drafted.

#### Step 2.6: Build and test

```bash
uv run dbt build \
  --project-dir .worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kipptaf \
  --select fct_behavioral_incidents+
```

Expected: model builds; `relationships` test on `staff_key` either passes or
warns with a count that matches the audit's unmatched DL users.

If unmatched count is non-zero, document it in the PR body (aggregates only) and
confirm severity matches sibling FK tests.

- [ ] Build green; test result understood.

#### Step 2.7: Commit

```bash
git -C .worktrees/cbini/fix/claude-identity-fk-orphans add \
  src/dbt/kipptaf/models/marts/facts/fct_behavioral_incidents.sql \
  src/dbt/kipptaf/models/marts/facts/properties/fct_behavioral_incidents.yml

git -C .worktrees/cbini/fix/claude-identity-fk-orphans commit -m \
  "fix(dbt): add staff_key FK to fct_behavioral_incidents via DeansList email join

Refs #3647."
```

- [ ] Committed.

---

### Task 3: Paterson 8 — investigate + fix or downgrade

**Files:**

- Probe: ad-hoc BigQuery (PR-branch CI schema, or local target if CI hasn't
  seeded yet)
- Modify (one of): `fct_assessment_scores_enrollment_scoped.sql`, upstream
  `int_*__all_assessments.sql`, or `fct_assessment_scores_enrollment_scoped.yml`
  (test downgrade).

#### Step 3.1: Reproduce the Paterson 8

```sql
select f.*
from `<schema>`.fct_assessment_scores_enrollment_scoped as f
left join `<schema>`.dim_students as d using (student_key)
left join `<schema>`.dim_assessment_administrations as da using (assessment_administration_key)
where f.student_key is not null and d.student_key is null and da.region = 'Paterson';
```

This returns row-level student data. Treat output as PII — capture in
`.claude/scratch/paterson-8.md` only. Aggregates / column-name references only
in PR body.

- [ ] 8 rows captured locally.

#### Step 3.2: Localize root cause

Inspect: are these `student_number` values present anywhere in `dim_students`
(current or historical)? Which `test_type` / `administration_window` are they
on? Are the students recent leavers (check
`int_powerschool__student_enrollments` or `dim_student_enrollments`)?

Categorize root cause into one of:

- A. Departed/historical students not present in current `dim_students` → fix is
  to extend `dim_students` coverage OR downgrade the FK test.
- B. Identifier mismatch (e.g., `student_number` typo, transposed source) → fix
  is in the upstream intermediate.
- C. Test-administration window edge case → fix is in
  `fct_assessment_scores_enrollment_scoped` enrollment-window logic.
- D. Something else → escalate with user.

- [ ] Root cause assigned.

#### Step 3.3: Decision — fix or downgrade

If A: confirm with user whether to extend `dim_students` coverage (potentially
out of scope) or downgrade the relationships test to `warn` with documented
rationale in the YAML and PR body. Default to downgrade if extending coverage
exceeds spec scope.

If B or C: fix at root, build affected models, confirm Paterson count drops
to 0.

If D: pause; do not commit.

- [ ] Path chosen and recorded.

#### Step 3.4: Apply fix or downgrade

For a fix, edit the upstream model. For a downgrade, edit
[.worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml](.worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml),
set the `student_key` relationships test to `severity: warn` with a `where`
clause excluding the documented Paterson cohort (or set a threshold), and add an
inline comment referencing
[#3863](https://github.com/TEAMSchools/teamster/issues/3863) with the rationale.

- [ ] Change drafted.

#### Step 3.5: Build and verify

```bash
uv run dbt build \
  --project-dir .worktrees/cbini/fix/claude-identity-fk-orphans/src/dbt/kipptaf \
  --select fct_assessment_scores_enrollment_scoped
```

Expected: build green; if fix path chosen, Paterson reproduce query returns 0;
if downgrade path chosen, test warns within documented threshold.

- [ ] Verified.

#### Step 3.6: Commit

```bash
git -C .worktrees/cbini/fix/claude-identity-fk-orphans add <changed-files>

git -C .worktrees/cbini/fix/claude-identity-fk-orphans commit -m \
  "fix(dbt): resolve Paterson student_key orphans in fct_assessment_scores_enrollment_scoped

Closes Paterson bucket in #3863."
```

Adjust the commit subject to reflect fix-vs-downgrade.

- [ ] Committed.

---

### Task 4: PR 1 — pre-merge checks and open PR

#### Step 4.1: Run the marts pre-merge checklist

Follow
[src/dbt/kipptaf/models/marts/CLAUDE.md](src/dbt/kipptaf/models/marts/CLAUDE.md)
"Pre-merge checklist (marts PRs)" section. Specifically:

- Scan `fct_behavioral_incidents` and `fct_assessment_scores_enrollment_scoped`
  for diamond paths.
- Scan touched models for column-naming rubric violations (R1–R10).
- Pull marts-model warnings from the latest CI run via
  `mcp__dbt__get_job_run_error` with `warning_only=true` after pushing.
- Scan the
  [project board](https://github.com/orgs/TEAMSchools/projects/4/views/1) for
  bonus issues incidentally resolved.

- [ ] Checklist complete; findings noted for PR body.

#### Step 4.2: Push branch

```bash
git -C .worktrees/cbini/fix/claude-identity-fk-orphans push -u origin cbini/fix/claude-identity-fk-orphans
```

- [ ] Pushed.

#### Step 4.3: Open PR 1

Use [.github/pull_request_template.md](.github/pull_request_template.md) as the
PR body. Title:
`fix(dbt): resolve cross-system identity FK orphans (FLEID, DeansList, Paterson 8)`.

Body must:

- Link `Closes #3863` and `Refs #3647`.
- Summarize audit findings (aggregates only — no names, IDs, emails).
- Note the Paterson 8 decision path (fix vs. downgrade with rationale).
- List any incidentally-resolved tracker issues from Step 4.1.

Use `mcp__github__create_pull_request`.

- [ ] PR 1 opened.

#### Step 4.4: Monitor dbt Cloud CI

Watch the CI run via `mcp__dbt__list_jobs_runs` / `mcp__dbt__get_job_run_error`
(with `warning_only=true`). Confirm the #3863 Miami orphans are gone and no new
mart warnings appeared.

- [ ] CI green; warnings reviewed.

---

## PR 2 — SmartRecruiters feasibility audit (doc-only)

### Task 5: SR feasibility audit and audit doc

**Files:**

- Probe: ad-hoc BigQuery (`stg_smartrecruiters__applicants`,
  `stg_smartrecruiters__applications`, ADP staff source)
- Create:
  `.worktrees/cbini/fix/claude-identity-fk-orphans/docs/superpowers/specs/2026-05-11-identity-fk-orphans-design.md`
  appendix OR new file
  `.worktrees/cbini/fix/claude-identity-fk-orphans/docs/superpowers/audits/2026-05-11-smartrecruiters-feasibility.md`
  (per spec, audit summary may also live in PR body; choose the lighter
  artifact)

#### Step 5.1: Pick deliverable location

Choose between (a) audit summary in PR body only, or (b) committed audit doc at
`docs/superpowers/audits/2026-05-11-smartrecruiters-feasibility.md`. Default to
(a) unless findings exceed a paragraph or include diagrams/tables that benefit
from being committed.

- [ ] Location chosen.

#### Step 5.2: Audit — email overlap, hired-candidate subset

```sql
with sr_hired as (
  select distinct lower(<sr_email_col>) as email
  from `teamster-332318`.kipptaf_smartrecruiters.stg_smartrecruiters__applicants
  where <hired_filter> -- e.g., status indicates hire
),
adp as (
  select distinct lower(<adp_email_col>) as email
  from `teamster-332318`.kipptaf_adp.<adp_associates_source>
  where <adp_email_col> is not null
)
select
  (select count(*) from sr_hired) as n_sr_hired,
  (select count(*) from adp) as n_adp,
  (select count(*) from sr_hired inner join adp using (email)) as n_matched_email_only;
```

Then layer in name + hire-date matching as a secondary probe to estimate the
fuzzy uplift over email alone. Substitute exact column / source names by
inspecting the SR staging models and ADP staff sources first.

- [ ] Email-only match rate captured. Fuzzy uplift estimated.

#### Step 5.3: Draft audit summary

Write (in PR body or audit doc per Step 5.1):

1. SR candidate population (count, hired vs. all).
2. ADP associate population (count).
3. Email-only match rate (numerator/denominator).
4. Estimated fuzzy uplift (name + hire-date).
5. Recommendation: (a) build a SR→ADP crosswalk model on email with a fuzzy
   fallback, (b) defer indefinitely (insufficient signal), or (c) alternate
   approach.
6. If (a): scope sketch and link to the follow-on issue (filed at Step 5.4).

No PII values — substitute column-name references and counts.

- [ ] Summary drafted.

#### Step 5.4: File follow-on issue (if applicable)

If recommendation is (a), file a new issue via `mcp__github__issue_write` titled
`feat(dbt): build SmartRecruiters → ADP candidate crosswalk`, labeled `dbt` +
`feat` + `smartrecruiters`, with a body that:

- References the audit summary (PR body or committed doc).
- Lists expected match rate (from audit aggregates).
- Defines acceptance: FK from `dim_job_candidates` /
  `fct_job_candidate_applications` to `dim_staff_work_assignments` for hired
  candidates with a documented match rate.

- [ ] Issue filed (or step skipped per audit decision).

#### Step 5.5: Commit audit doc (if Step 5.1 chose committed doc)

```bash
git -C .worktrees/cbini/fix/claude-identity-fk-orphans add \
  docs/superpowers/audits/2026-05-11-smartrecruiters-feasibility.md

git -C .worktrees/cbini/fix/claude-identity-fk-orphans commit -m \
  "docs(audits): SmartRecruiters → ADP candidate matching feasibility

Refs #3647."
```

Skip if Step 5.1 chose PR-body-only.

- [ ] Committed (or skipped).

#### Step 5.6: Open PR 2

Branch off the same `cbini/fix/claude-identity-fk-orphans` after PR 1 merges, OR
(if PRs need to be parallel) cut a sibling branch
`cbini/feat/claude-smartrecruiters-feasibility-audit` from `main` for PR 2.
Default to sequential (after PR 1 merges) to keep the tracker simple.

PR title:
`feat(dbt): SmartRecruiters → ADP candidate matching feasibility audit`. Body
uses [.github/pull_request_template.md](.github/pull_request_template.md), links
`Closes #3647` and references any follow-on issue from Step 5.4.

Use `mcp__github__create_pull_request`.

- [ ] PR 2 opened.

---

## Verification (end-to-end)

- [ ] [#3863](https://github.com/TEAMSchools/teamster/issues/3863) reproduce
      query returns 0 Miami rows in PR 1's dbt Cloud CI schema.
- [ ] Paterson 8 either resolved to 0 rows or test downgraded with rationale
      documented in PR 1.
- [ ] `fct_behavioral_incidents.staff_key` relationships test exists and
      passes/warns within audit-documented threshold.
- [ ] PR 1 merges; PR 2 opens with audit findings; SR build follow-on issue
      exists (or audit explicitly rejects build).
- [ ] Both PRs apply the marts pre-merge checklist before final review.
