# KFWD Career Launch Survey Tableau Additions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich `rpt_tableau__kfwd_career_launch_survey` with 5 alumni
demographic columns already surfaced in the AppSheet report and 8
career-conversation fields from the KFWD AppSheet app.

**Architecture:** All changes land in one dbt model
(`rpt_tableau__kfwd_career_launch_survey`, a contract-enforced view in
`kipptaf_extracts`/tableau schema) and its properties YAML. Demographic columns
come straight off `int_kippadb__roster`, which the model's `roster` CTE already
joins — no new join. Career-conversation fields add one `left join` to
`stg_google_appsheet__kfwd_career_conversations__output` (unique on
`contact_id`, so no fan-out) inside the `roster` CTE, mirroring the existing
`programs` join pattern, with booleans coalesced to `false` at the join site
(the `coalesce(p.is_basta, false)` precedent).

**Tech Stack:** dbt (kipptaf project), BigQuery, sqlfmt/sqlfluff via trunk.

## Global Constraints

- The model is contract-enforced: every new SQL column MUST be declared in the
  properties YAML with matching name + `data_type`, or the build fails.
- Repo SQL conventions (`src/dbt/CLAUDE.md`): ST06 column ordering (plain refs
  grouped by source table first, then simple functions like `coalesce`), no
  `QUALIFY`, no `ORDER BY`, trailing commas, 88-char lines. Do not hand-fight
  formatting — the pre-commit trunk hook runs sqlfmt.
- Do NOT join `rpt_appsheet__kfwd_career_launch_survey` or any other rpt model —
  demographic columns must come from `int_kippadb__roster` directly.
- Validation builds use `--target dev` with `--defer --state target/prod` (path
  relative to `--project-dir`). Never `--target prod`.
- PII note: phone/notes columns stay in the warehouse/Tableau extract — do not
  paste row values into commits, PR bodies, or issues.

---

### Task 1: Add roster demographic columns

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__kfwd_career_launch_survey.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__kfwd_career_launch_survey.yml`

**Interfaces:**

- Consumes: `int_kippadb__roster` columns `ktc_cohort`,
  `contact_currently_enrolled_school`, `contact_current_college_cumulative_gpa`,
  `contact_mobile_phone`, `contact_home_phone` (all already available via the
  existing `r` alias in the `roster` CTE).
- Produces: report columns `ktc_cohort` (int64), `currently_enrolled_school`
  (string), `current_college_cumulative_gpa` (numeric), `primary_phone`
  (string), `secondary_phone` (string). Aliases match the AppSheet report
  (`rpt_appsheet__kfwd_career_launch_survey`) for consistency.

- [ ] **Step 1: Add the columns to the `roster` CTE**

In the `roster` CTE of `rpt_tableau__kfwd_career_launch_survey.sql`, the `r.`
plain-ref group currently ends with:

```sql
            r.contact_middle_school_attended as middle_school_attended,
            r.contact_high_school_graduated_from as high_school_graduated_from,
```

Append after that line:

```sql
            r.ktc_cohort,
            r.contact_currently_enrolled_school as currently_enrolled_school,
            r.contact_current_college_cumulative_gpa
            as current_college_cumulative_gpa,
            r.contact_mobile_phone as primary_phone,
            r.contact_home_phone as secondary_phone,
```

(sqlfmt may re-wrap the long alias line at commit time; that's fine.)

- [ ] **Step 2: Add the columns to the final SELECT**

In the final `select`, the `r.` group currently ends with:

```sql
    r.middle_school_attended,
    r.high_school_graduated_from,
```

Append after that line:

```sql
    r.ktc_cohort,
    r.currently_enrolled_school,
    r.current_college_cumulative_gpa,
    r.primary_phone,
    r.secondary_phone,
```

- [ ] **Step 3: Declare the columns in the properties YAML**

In
`src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__kfwd_career_launch_survey.yml`,
append to the end of the `columns:` list (contract matching is by name + type,
not order; recent additions with descriptions live at the bottom):

```yaml
- name: ktc_cohort
  data_type: int64
  description:
    KIPP-to-college cohort year for the alumnus, from their Salesforce contact
    record.
- name: currently_enrolled_school
  data_type: string
  description:
    School the alumnus is currently enrolled in, from their Salesforce contact
    record.
- name: current_college_cumulative_gpa
  data_type: numeric
  description:
    Current cumulative college GPA, from the alumnus's Salesforce contact
    record.
- name: primary_phone
  data_type: string
  description: Mobile phone from the alumnus's Salesforce contact record.
- name: secondary_phone
  data_type: string
  description: Home phone from the alumnus's Salesforce contact record.
```

- [ ] **Step 4: Parse to catch syntax/contract-declaration errors**

Run from the repo root:

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
```

Expected: completes without errors.

- [ ] **Step 5: Build the model against dev with prod defer**

```bash
uv run dbt build --select rpt_tableau__kfwd_career_launch_survey \
  --target dev --defer --state target/prod --project-dir src/dbt/kipptaf
```

Expected: model builds PASS (contract enforced) and the existing
`dbt_utils.unique_combination_of_columns` test on (`contact_id`, `response_id`)
passes — confirming no grain change.

- [ ] **Step 6: Spot-check the new columns**

Query the dev relation (BigQuery MCP), e.g.:

```sql
select
    count(*) as row_count,
    count(ktc_cohort) as ktc_cohort_populated,
    count(currently_enrolled_school) as school_populated,
    count(primary_phone) as phone_populated,
from `teamster-332318`.`zz_<dev_schema>_kipptaf_tableau`.rpt_tableau__kfwd_career_launch_survey
```

Expected: non-zero populated counts; `row_count` matches the prod model's
current row count (no fan-out).

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__kfwd_career_launch_survey.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__kfwd_career_launch_survey.yml
git commit -m "feat(kipptaf): add roster demographic columns to kfwd career launch survey"
```

---

### Task 2: Add career-conversation fields

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__kfwd_career_launch_survey.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__kfwd_career_launch_survey.yml`

**Interfaces:**

- Consumes: `stg_google_appsheet__kfwd_career_conversations__output` — one row
  per `contact_id` (`unique` + `not_null` tested), columns `notes` (string) and
  7 booleans `is_resume_score`, `is_linkedin`, `is_mock_interview_or_prep`,
  `is_professional_references_list`, `is_job_search_template`,
  `is_cover_letter_template`, `is_work_samples`.
- Produces: report columns `career_conversation_notes` (string, NULL when no
  conversation record) and the 7 `is_*` booleans (false when no conversation
  record, matching the `is_basta` precedent). Unmatched survey-only rows in the
  full join get NULL for all 8, same as every other roster-side column.

- [ ] **Step 1: Add the join in the `roster` CTE**

After the existing line:

```sql
        left join programs as p on r.contact_id = p.student
```

add:

```sql
        left join
            {{ ref("stg_google_appsheet__kfwd_career_conversations__output") }} as cc
            on r.contact_id = cc.contact_id
```

- [ ] **Step 2: Add the `notes` column to the `roster` CTE plain-ref section**

After the existing line:

```sql
            p.college_programs,
```

add:

```sql
            cc.notes as career_conversation_notes,
```

- [ ] **Step 3: Add the coalesced booleans to the `roster` CTE**

After the existing block:

```sql
            coalesce(p.is_kippnj_internship, false) as is_kippnj_internship,
```

add:

```sql
            coalesce(cc.is_resume_score, false) as is_resume_score,
            coalesce(cc.is_linkedin, false) as is_linkedin,
            coalesce(
                cc.is_mock_interview_or_prep, false
            ) as is_mock_interview_or_prep,
            coalesce(
                cc.is_professional_references_list, false
            ) as is_professional_references_list,
            coalesce(cc.is_job_search_template, false) as is_job_search_template,
            coalesce(
                cc.is_cover_letter_template, false
            ) as is_cover_letter_template,
            coalesce(cc.is_work_samples, false) as is_work_samples,
```

(sqlfmt may collapse/re-wrap the multi-line `coalesce` calls at commit time.)

- [ ] **Step 4: Add the columns to the final SELECT**

After the Task 1 additions ending with:

```sql
    r.secondary_phone,
```

add:

```sql
    r.career_conversation_notes,
    r.is_resume_score,
    r.is_linkedin,
    r.is_mock_interview_or_prep,
    r.is_professional_references_list,
    r.is_job_search_template,
    r.is_cover_letter_template,
    r.is_work_samples,
```

- [ ] **Step 5: Declare the columns in the properties YAML**

Append to the end of the `columns:` list:

```yaml
- name: career_conversation_notes
  data_type: string
  description:
    Free-text notes from the alumnus's KFWD career conversation, logged in the
    KFWD AppSheet app. NULL when no conversation is recorded.
- name: is_resume_score
  data_type: boolean
  description:
    Whether a resume was scored during the KFWD career conversation. False when
    no conversation is recorded.
- name: is_linkedin
  data_type: boolean
  description:
    Whether the alumnus's LinkedIn profile was discussed during the KFWD career
    conversation. False when no conversation is recorded.
- name: is_mock_interview_or_prep
  data_type: boolean
  description:
    Whether mock interview or interview preparation was discussed during the
    KFWD career conversation. False when no conversation is recorded.
- name: is_professional_references_list
  data_type: boolean
  description:
    Whether the professional references list was discussed during the KFWD
    career conversation. False when no conversation is recorded.
- name: is_job_search_template
  data_type: boolean
  description:
    Whether the job search template was discussed during the KFWD career
    conversation. False when no conversation is recorded.
- name: is_cover_letter_template
  data_type: boolean
  description:
    Whether the cover letter template was discussed during the KFWD career
    conversation. False when no conversation is recorded.
- name: is_work_samples
  data_type: boolean
  description:
    Whether work samples were discussed during the KFWD career conversation.
    False when no conversation is recorded.
```

- [ ] **Step 6: Parse, then build with defer**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
uv run dbt build --select rpt_tableau__kfwd_career_launch_survey \
  --target dev --defer --state target/prod --project-dir src/dbt/kipptaf
```

Expected: build PASS, uniqueness test on (`contact_id`, `response_id`) PASS (the
staging model is unique on `contact_id`, so the join cannot fan out).

- [ ] **Step 7: Spot-check the join**

Query the dev relation and compare against the staging model:

```sql
select
    (
        select count(*)
        from `teamster-332318`.kipptaf_google.stg_google_appsheet__kfwd_career_conversations__output
    ) as staging_contacts,
    count(distinct if(rn.career_conversation_notes is not null
        or rn.is_resume_score, rn.contact_id, null)) as matched_contacts,
from `teamster-332318`.`zz_<dev_schema>_kipptaf_tableau`.rpt_tableau__kfwd_career_launch_survey as rn
```

Expected: `matched_contacts` is close to `staging_contacts` (contacts absent
from the roster — e.g. wrong `ktc_status` — legitimately don't match; a large
gap warrants investigation before proceeding). Adjust the staging schema name if
the prod relation lives elsewhere (`dbt ls` or `INFORMATION_SCHEMA` will
confirm).

- [ ] **Step 8: Lint the changed files**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__kfwd_career_launch_survey.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__kfwd_career_launch_survey.yml
```

Expected: no new issues (pre-commit only runs fmt; sqlfluff/yamllint fire at
pre-push/CI, so check now).

- [ ] **Step 9: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__kfwd_career_launch_survey.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__kfwd_career_launch_survey.yml
git commit -m "feat(kipptaf): add kfwd career conversation fields to career launch survey"
```
