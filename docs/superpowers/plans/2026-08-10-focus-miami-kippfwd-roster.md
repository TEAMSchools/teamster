# Focus Sourcing for `rpt_gsheets__kippfwd_miami_roster` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-source `rpt_gsheets__kippfwd_miami_roster` from kipptaf's existing
Focus layer so it keeps producing data after Miami PowerSchool goes dark past
`academic_year = 2025`.

**Architecture:** A rewrite of one reporting view. It joins three existing
kipptaf models — `int_focus__student_enrollments`, `int_focus__students`, and
`int_focus__student_contacts` — keeps the FLDOE FAST pivots, and retains one
PowerSchool join for `previous_year_ada`. No new models, no new sources.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, sqlfluff and markdownlint via
trunk.

- **Spec:**
  `docs/superpowers/specs/2026-08-10-focus-miami-kippfwd-roster-design.md`
- **Issue:** [#4782](https://github.com/TEAMSchools/teamster/issues/4782)
- **Related:** [#4794](https://github.com/TEAMSchools/teamster/issues/4794)
  (upstream `enroll_status` defect),
  [#4795](https://github.com/TEAMSchools/teamster/issues/4795) (advisor),
  [#4796](https://github.com/TEAMSchools/teamster/issues/4796) (GPA replacement)

## Global Constraints

- **Worktree:** `/workspaces/teamster/.worktrees/focus-miami-kippfwd-roster`.
  Every `git` call uses `git -C <worktree>`; every `dbt` call uses
  `--project-dir <worktree>/src/dbt/kipptaf`. Read, Edit, and Write must target
  paths under the worktree, never `/workspaces/teamster/src/...` — the main
  checkout sits on a different, older branch and does not reflect `main`.
- **Never run bare `python` or `dbt`** — always `uv run dbt ...`.
- **`--state` must be the absolute main-repo path**
  `/workspaces/teamster/src/dbt/kipptaf/target/prod`.
- **The output contract does not change.** All 30 columns keep their existing
  names, types, and **select order**. The properties yml `columns:` block gains
  descriptions and one model-level test, but no column additions or removals.
- **SQL style** (`.trunk/config/.sqlfluff`): BigQuery dialect, trailing commas
  in `SELECT`, single quotes, 88-character lines, no `ORDER BY`, no
  `GROUP BY ALL`, no `SELECT *` in a final `rpt_` select.
- **ST09 join order:** ON-clause predicates put the earlier-referenced table on
  the left.
- **Do not run `trunk fmt`.** The pre-commit hook formats at commit time. Run
  `trunk check --force --no-fix </dev/null <files>` with cwd set to the
  worktree. `--force` is required; `--no-fix </dev/null` avoids an interactive
  hang. Binary: `/workspaces/teamster/.trunk/tools/trunk`, falling back to
  `~/.cache/trunk/launcher/trunk`. Expect `unformatted files` on a first check —
  the commit hook fixes those. Only `file:line` findings naming a rule are real.
- **`git add` names specific files.** Never `-u`, `-A`, or `.`.
- **Two naming traps.** `int_focus__student_enrollments.student_number` is the
  **Focus** `student_id`, not PowerSchool's `student_number`. And
  `int_focus__student_contacts.sort_order` is a STRING.

---

## File Structure

| File                                                                                             | Responsibility                                                                                   |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql`            | The reporting view — joins the three Focus models, the FAST pivots, and the PowerSchool ADA join |
| `src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__kippfwd_miami_roster.yml` | Contract columns plus descriptions and the scoped uniqueness test                                |

---

### Task 1: Rewrite the reporting view

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql`
  (full rewrite)
- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__kippfwd_miami_roster.yml`

**Interfaces:**

- Consumes: `ref("int_focus__student_enrollments")`,
  `ref("int_focus__students")`, `ref("int_focus__student_contacts")`,
  `ref("stg_fldoe__fast")`, `ref("int_extracts__student_enrollments")`.
- Produces: the unchanged 30-column contract consumed by the
  `gsheets__kippfwd_miami_roster` exposure. Task 2 verifies it.

- [ ] **Step 1: Install packages in the worktree**

A fresh worktree has no `dbt_packages/`, and every later `dbt` call fails
without them.

```bash
uv run dbt deps \
  --project-dir /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster/src/dbt/kipptaf
```

Expected: `Installing ...` then `Installed from version ...` per package.

- [ ] **Step 2: Rewrite the model**

Replace the entire contents of
`src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql`.

The `ST06` ignore is deliberate — the select order is the Google Sheet's column
order and must not be reshuffled to satisfy the linter.

```sql
with
    fast_concat as (
        select
            student_id,
            academic_year,

            concat(achievement_level, ' (', scale_score, ')') as fast_score,
            lower(concat(discipline, '_', administration_window)) as pivot_column,
        from {{ ref("stg_fldoe__fast") }}
    ),

    fast_pivot as (
        select
            student_id,
            academic_year,
            ela_pm1,
            ela_pm2,
            ela_pm3,
            math_pm1,
            math_pm2,
            math_pm3,
        from
            fast_concat pivot (
                max(fast_score) for pivot_column
                in ('ela_pm1', 'ela_pm2', 'ela_pm3', 'math_pm1', 'math_pm2', 'math_pm3')
            )
    ),

    /* TODO(#4794): int_focus__student_enrollments.enroll_status derives from
       drop-code presence, and Focus stamps W01/W02 rollover codes on nearly
       every span at year end -- it reads 361 of 365 AY2025 students as
       transferred out. Derive locally until that is fixed upstream, then
       delete these two CTEs and read the upstream column. Anchor on the max
       academic_year in Focus, NOT var("current_academic_year"), which lags the
       July rollover. */
    latest_year as (
        select max(academic_year) as academic_year,
        from {{ ref("int_focus__student_enrollments") }}
    ),

    open_enrollment as (
        select distinct e.student_number,
        from {{ ref("int_focus__student_enrollments") }} as e
        inner join latest_year as ly on e.academic_year = ly.academic_year
        where e.exitcode is null
    ),

    contact_1 as (
        select student_id, contact_name, email, phone_home, phone_mobile,
        from {{ ref("int_focus__student_contacts") }}
        where sort_order = '1'
    ),

    contact_2 as (
        select student_id, contact_name, email, phone_home, phone_mobile,
        from {{ ref("int_focus__student_contacts") }}
        where sort_order = '2'
    )

-- trunk-ignore(sqlfluff/ST06): select order is the Google Sheet column order
select
    e.academic_year,
    e.student_name as lastfirst,

    /* TODO(#4795): Focus has no advisory structure for grades 7-8 */
    cast(null as string) as advisor_lastfirst,

    s.powerschool_id as ps_id,

    lpad(cast(s.disis_id as string), 7, '0') as mdcps_id,

    regexp_extract(s.sex_label, r'\[(\w)\]') as gender,

    if(s.ese_fefp_code is not null, 'Has IEP', 'No IEP') as iep_status,

    c1.contact_name as contact_1_name,
    c1.phone_home as contact_1_phone_home,
    c1.phone_mobile as contact_1_phone_mobile,
    c1.email as contact_1_email_current,

    c2.contact_name as contact_2_name,
    c2.phone_home as contact_2_phone_home,
    c2.phone_mobile as contact_2_phone_mobile,
    c2.email as contact_2_email_current,

    case
        when e.startdate > current_date('{{ var("local_timezone") }}')
        then -1
        when e.enroll_status = 3
        then 3
        when oe.student_number is not null
        then 0
        else 2
    end as enroll_status,

    e.grade_level,

    fp.ela_pm1,
    fp.ela_pm2,
    fp.ela_pm3,
    fp.math_pm1,
    fp.math_pm2,
    fp.math_pm3,

    /* TODO(#4796): Miami middle school no longer produces a GPA; awaiting a
       replacement academic-standing metric from KIPP Forward */
    cast(null as float64) as gpa_cumulative,

    ada.ada_unweighted_year_prev as previous_year_ada,

    e.fteid as fleid,

    /* TODO(#4796): see gpa_cumulative above */
    cast(null as float64) as gpa_y1,

    fp_prev.ela_pm3 as ela_pm3_prev,
    fp_prev.math_pm3 as math_pm3_prev,
from {{ ref("int_focus__student_enrollments") }} as e
left join {{ ref("int_focus__students") }} as s on e.student_number = s.student_id
left join open_enrollment as oe on e.student_number = oe.student_number
left join contact_1 as c1 on e.student_number = c1.student_id
left join contact_2 as c2 on e.student_number = c2.student_id
left join
    fast_pivot as fp
    on e.fteid = fp.student_id
    and e.academic_year = fp.academic_year
left join
    fast_pivot as fp_prev
    on e.fteid = fp_prev.student_id
    and e.academic_year - 1 = fp_prev.academic_year
left join
    {{ ref("int_extracts__student_enrollments") }} as ada
    on s.powerschool_id = ada.student_number
    and e.academic_year = ada.academic_year
    and ada.region = 'Miami'
    and ada.rn_year = 1
where
    e.rn_year = 1
    and e.grade_level in (7, 8)
    and e.academic_year >= {{ var("current_academic_year") - 1 }}
```

- [ ] **Step 3: Add descriptions and the uniqueness test to the properties yml**

Keep every existing `- name:` / `data_type:` pair exactly as it is, in its
current order — the contract must not change. Add a model-level `description:`
and `data_tests:` block above `columns:`, and a `description:` under each
existing column.

The uniqueness test is scoped because the contract exposes no column that is
both unique and non-null — `ps_id` is null for post-cutover enrollees, and
`fleid` is null for a handful of students.

```yaml
models:
  - name: rpt_gsheets__kippfwd_miami_roster
    description: >-
      KIPP Forward Miami grades 7 and 8 roster, one row per student per academic
      year for the current and prior year. Enrollment, identity, demographics,
      and guardian contacts come from Focus; FAST scores from FLDOE; and
      prior-year ADA from PowerSchool, which holds no Miami data past academic
      year 2025. Advisor and both GPA columns are cast null - Focus has no grade
      7-8 advisory structure, and Miami middle school no longer produces a GPA.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - academic_year
              - fleid
          config:
            severity: error
            where: fleid is not null
    columns:
      - name: academic_year
        description: School year start year, 2026 = 2026-27.
        data_type: int64
```

Continue the remaining 29 columns in their existing order. Write each
description from what the column actually holds. For the three null-cast
columns, state that the value is not sourced and why, without putting the issue
number in the description — the issue reference belongs in the SQL comment. Tag
PII columns with `config.meta.contains_pii: true`: `lastfirst`, `ps_id`,
`mdcps_id`, `fleid`, and all eight `contact_*` columns.

- [ ] **Step 4: Build the model and its test**

```bash
uv run dbt build --select rpt_gsheets__kippfwd_miami_roster \
  --project-dir /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster/src/dbt/kipptaf \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: `PASS` on the model and its uniqueness test. A contract error naming a
column means the SQL's type drifted from the yml — change the SQL, not the
contract.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix </dev/null \
  src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql \
  src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__kippfwd_miami_roster.yml
git -C /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster add \
  src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql \
  src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__kippfwd_miami_roster.yml
git -C /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster commit \
  -m "feat(kipptaf): source kippfwd miami roster from focus

Closes #4782"
```

---

### Task 2: Parity verification

**Files:**

- No file changes. This task gates the PR.

**Interfaces:**

- Consumes: the dev-schema build from Task 1.
- Produces: a go or no-go on opening the PR.

Substitute your own dev schema (shown in the Task 1 build output) for
`zz_<user>_kipptaf_extracts` throughout.

- [ ] **Step 1: Row-count parity for the PowerSchool-era year**

The prod side is the current model, still PowerSchool-sourced.

```sql
select 'new' as build, academic_year, count(*) as n
from `teamster-332318`.`zz_<user>_kipptaf_extracts`.`rpt_gsheets__kippfwd_miami_roster`
where academic_year = 2025
group by build, academic_year
union all
select 'prod' as build, academic_year, count(*) as n
from `teamster-332318`.`kipptaf_extracts`.`rpt_gsheets__kippfwd_miami_roster`
where academic_year = 2025
group by build, academic_year
```

Expected: 365 on both sides.

- [ ] **Step 2: The enroll_status regression check**

This is the single most important check in the plan. It confirms the local
derivation beat the broken upstream column.

```sql
select academic_year, enroll_status, count(*) as n
from `teamster-332318`.`zz_<user>_kipptaf_extracts`.`rpt_gsheets__kippfwd_miami_roster`
where academic_year = 2025
group by academic_year, enroll_status
```

Expected: near 222 at `0` and 143 at `2`, matching PowerSchool. If it reads near
361 at `2`, the local derivation is not taking effect and the model is reading
the upstream column — re-read the `open_enrollment` CTE and its join.

- [ ] **Step 3: Confirm AY2026 rows exist**

The whole point of the change, and not checkable against prod.

```sql
select academic_year, grade_level, count(*) as n
from `teamster-332318`.`zz_<user>_kipptaf_extracts`.`rpt_gsheets__kippfwd_miami_roster`
where academic_year = 2026
group by academic_year, grade_level
```

Expected: roughly 194 in grade 7 and 179 in grade 8. Zero rows means the
`academic_year >= current_academic_year - 1` filter excluded them because the
var still reads 2025 — correct behavior for today. Note which case you got in
the PR body.

- [ ] **Step 4: Identity and contact coverage**

```sql
select
    count(*) as n,
    countif(ps_id is not null) as has_ps_id,
    countif(fleid is not null) as has_fleid,
    countif(mdcps_id is not null) as has_mdcps_id,
    countif(contact_1_name is not null) as c1_name,
    countif(contact_1_email_current is not null) as c1_email,
    countif(contact_1_phone_mobile is not null) as c1_mobile,
    countif(contact_1_phone_home is not null) as c1_home,
    countif(contact_2_name is not null) as c2_name
from `teamster-332318`.`zz_<user>_kipptaf_extracts`.`rpt_gsheets__kippfwd_miami_roster`
where academic_year = 2026
```

Expected: `c1_name` near 338, `c1_email` near 328, `c1_mobile` near 279,
`c1_home` near 55, `c2_name` near 283. A low `c1_home` is expected, not a bug —
Focus mostly stores mobile numbers. `has_ps_id` will fall short of `n` by
roughly 80 across both years; those are post-cutover enrollees.

- [ ] **Step 5: Confirm no fan-out from the contact joins**

`int_focus__student_contacts` is one row per (student, contact), so a mistake in
the `sort_order` CTEs multiplies rows.

```sql
select count(*) as rows_out, count(distinct format('%T|%T', academic_year, fleid)) as distinct_keys
from `teamster-332318`.`zz_<user>_kipptaf_extracts`.`rpt_gsheets__kippfwd_miami_roster`
where fleid is not null
```

Expected: the two numbers are equal.

- [ ] **Step 6: Open the pull request**

Use `.github/pull_request_template.md` as the body. Include the Step 1 through
Step 5 numbers. Call out that `advisor_lastfirst`, `gpa_cumulative`, and
`gpa_y1` now return null, linking #4795 and #4796, and that `enroll_status` is
derived locally pending #4794. Reference `Closes #4782`.

Do not run `gh project item-add` on the PR — the issue reference in the body
puts it on the board.

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: the column mapping,
contacts, retained PowerSchool join, null casts, and the local `enroll_status`
derivation to Task 1; the testing and manual verification list to Task 2. The
spec's "Out of scope" items intentionally have no task.

**Type consistency.** `e.student_number` (Focus student id) joins to
`s.student_id` and `c*.student_id`. `s.powerschool_id` joins to
`ada.student_number` (PowerSchool). `e.fteid` joins to `fp.student_id`.
`sort_order` is compared to string literals. `grade_level` is already INT64
upstream, so no cast.

**Known soft spot.** Task 1 Step 3 describes the remaining 29 column
descriptions rather than spelling out all 29. The existing yml already holds
every name and `data_type`, and the descriptions are mechanical statements of
what each column holds.
