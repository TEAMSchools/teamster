# OKRTS Behavior Taxonomy Retrofit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `rpt_tableau__okrts_behavior` carry the old and new NJ culture
taxonomies at once, so the OKRTS Dashboard shows AY2026 corrective behaviors
without breaking any AY2025 view.

**Architecture:** Replace the model's two drifting literal lists — a category
allowlist and a `category_type` CASE — with a single derivation plus a
`category_type is not null` filter, which makes the drift that caused this bug
structurally impossible. Expose the raw `behavior_category` so the workbook can
separate the three `Values` families. Exclude Miami's stopped DeansList feed
from AY2026 forward through a macro and a var, applied in an outer select so
window functions keep their semantics.

**Tech Stack:** dbt (BigQuery), Jinja macros, `uv run` for every command.

**Spec:**
`docs/superpowers/specs/2026-08-28-okrts-behavior-taxonomy-retrofit-design.md`

## Global Constraints

- **Worktree:**
  `/workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy`.
  Every git call uses `git -C <worktree>`. Every dbt call uses
  `--project-dir <worktree>/src/dbt/kipptaf`. Bare `git` from the main repo
  commits to `main`.
- **Scope is `kipptaf` only.** Do not touch the district projects or the shared
  `deanslist` package.
- **Contracts are enforced** on `models/extracts/**` by inheritance from
  `extracts: +contract: enforced: true`. Any new column needs a `data_type` in
  the model's yml or the build fails hard. Contracts match on name and type, not
  order.
- **Run builds in the FOREGROUND.** Never background a `dbt build`.
- **Never run two dbt commands concurrently** against this worktree — they share
  `target/` and corrupt the partial-parse manifest.
- **`current_academic_year` is 2026.** The Miami cutover year is a literal in a
  var, never `var("current_academic_year")` — it marks a historical event and
  must not move when the var rolls over in July.
- **Do not run `trunk fmt` or `trunk check` manually** for `.sql` files; the
  pre-commit hook formats. For the plan/spec `.md` only, use
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix </dev/null`
  with cwd set to the worktree.
- Commit messages use conventional commits and end with `Refs #5062`.

## File Structure

| File                                                              | Responsibility                                        | Task |
| ----------------------------------------------------------------- | ----------------------------------------------------- | ---- |
| `src/dbt/kipptaf/dbt_project.yml`                                 | `deanslist_stopped_code_locations` var                | 1    |
| `src/dbt/kipptaf/macros/utils.sql`                                | `exclude_deanslist_stopped` macro                     | 1    |
| `.../extracts/tableau/rpt_tableau__suspension_over_time.sql`      | Miami exclusion; proves the macro                     | 1    |
| `.../extracts/tableau/rpt_tableau__okrts_behavior.sql`            | Taxonomy derivation, new column, normalization, Miami | 2    |
| `.../extracts/tableau/properties/rpt_tableau__okrts_behavior.yml` | `behavior_category` contract entry                    | 2    |
| `.../extracts/tableau/rpt_tableau__okrts_referrals.sql`           | Miami exclusion preserving `is_week_ytd`              | 3    |
| `src/dbt/kipptaf/models/exposures/tableau.yml`                    | `okrts_dashboard` lineage fix                         | 4    |

---

## Tasks

### Task 1: `exclude_deanslist_stopped` macro, var, and first consumer

**Files:**

- Modify: `src/dbt/kipptaf/dbt_project.yml` (vars block, after
  `frozen_powerschool_code_locations`)
- Modify: `src/dbt/kipptaf/macros/utils.sql` (append)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__suspension_over_time.sql`

**Interfaces:**

- Produces: `exclude_deanslist_stopped(project_column, year_column)` — a Jinja
  macro rendering a boolean SQL predicate. Tasks 2 and 3 call it as
  `{{ exclude_deanslist_stopped("_dbt_source_project", "academic_year") }}`.
  Renders `true` when the var is empty.
- Produces: the `select * except (_dbt_source_project)` outer-select pattern
  that Tasks 2 and 3 repeat.

`rpt_tableau__suspension_over_time` is the smallest of the three consumers, so
it proves the macro compiles and builds before the larger models depend on it.

- [ ] **Step 1: Add the var**

In `src/dbt/kipptaf/dbt_project.yml`, immediately after the
`frozen_powerschool_code_locations` line:

```yaml
# Code locations whose DeansList feed has stopped, mapped to the first academic
# year to exclude. These locations stay in the enrollment spine, so extracts
# that left-join it would otherwise render a stopped feed as zero activity
# rather than no data. Year-scoped on purpose -- history before the cutover has
# to stay readable. Miami's last behavior row is 2026-06-25; its replacement
# behavior platform lands in Q2 and this entry comes out then. See #5062.
deanslist_stopped_code_locations:
  kippmiami: 2026
```

- [ ] **Step 2: Add the macro**

Append to `src/dbt/kipptaf/macros/utils.sql`:

```sql
{# Drops a code location from its DeansList cutover year onward. Unlike
   exclude_frozen this is year-scoped: the location's history before the cutover
   stays readable. Apply it in an OUTER select, after any window function --
   filtering inside the same query block changes window partitions and silently
   alters columns for the years you meant to keep. Add or remove a location in
   the deanslist_stopped_code_locations var. #}
{% macro exclude_deanslist_stopped(project_column, year_column) -%}
    {%- set stopped = var("deanslist_stopped_code_locations", {}) -%}
    {%- if not stopped -%}
        true
    {%- else -%}
        not (
            {%- for location, first_year in stopped.items() %}
            {%- if not loop.first %} or {% endif %}
            (
                {{ project_column }} = '{{ location }}'
                and {{ year_column }} >= {{ first_year }}
            )
            {%- endfor %}
        )
    {%- endif -%}
{%- endmacro %}
```

- [ ] **Step 3: Verify the project parses**

```bash
uv run dbt parse --project-dir \
  /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy/src/dbt/kipptaf
```

Expected: completes with no Jinja error. A syntax error in the macro fails here.

- [ ] **Step 4: Wrap `rpt_tableau__suspension_over_time` in a CTE**

In that file, the final `select` currently begins `select co.student_number,`
and ends with
`where co.rn_year = 1 and co.academic_year >= {{ var("current_academic_year") - 1 }}`.

Convert it to a named CTE and add an outer select. Add `co._dbt_source_project`
as the first projected column of the CTE (the `except` in the outer select keeps
it out of the contract), close the CTE with `)`, then append:

```sql
select * except (_dbt_source_project),
from suspension_days
where {{ exclude_deanslist_stopped("_dbt_source_project", "academic_year") }}
```

The CTE is named `suspension_days`. The existing `suspension_dates` CTE and
every join stay exactly as they are.

- [ ] **Step 5: Confirm the macro renders correct SQL**

```bash
uv run dbt compile --project-dir \
  /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy/src/dbt/kipptaf \
  --select rpt_tableau__suspension_over_time
```

Then read the tail of
`src/dbt/kipptaf/target/compiled/kipptaf/models/extracts/tableau/rpt_tableau__suspension_over_time.sql`.

Expected, verbatim:

```sql
where not (
            (
                _dbt_source_project = 'kippmiami'
                and academic_year >= 2026
            ))
```

Whitespace may differ. If it renders `true`, the var is not being read — stop
and fix Step 1.

- [ ] **Step 6: Build**

```bash
uv run dbt build --project-dir \
  /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy/src/dbt/kipptaf \
  --select rpt_tableau__suspension_over_time
```

Expected: PASS. A contract violation here means `_dbt_source_project` leaked
into the output — check the `except`.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy \
  add src/dbt/kipptaf/dbt_project.yml src/dbt/kipptaf/macros/utils.sql \
      src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__suspension_over_time.sql
git -C /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy \
  commit -m "feat(dbt): add exclude_deanslist_stopped macro and drop Miami from AY2026 suspensions

Refs #5062"
```

---

### Task 2: Rebuild the taxonomy in `rpt_tableau__okrts_behavior`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__okrts_behavior.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__okrts_behavior.yml`

**Interfaces:**

- Consumes: `exclude_deanslist_stopped` from Task 1.
- Produces: a `behavior_category` column (`string`) in the extract, and a
  `category_type` domain of exactly `BEAT`, `Corrective`,
  `Habits of Excellence`.

- [ ] **Step 1: Replace the `behaviors` CTE with a two-stage derivation**

Replace the whole `behaviors as (...)` CTE — from `with behaviors as (` through
the closing `),` before `behavior_aggregation` — with:

```sql
with
    behaviors_typed as (
        select
            b._dbt_source_relation,
            b._dbt_source_project,
            b.dl_said,
            b.school_name,
            b.student_school_id,
            b.behavior_date,
            b.behavior_category,
            b.point_value,
            b.staff_full_name as entry_staff,

            /* Miami and New Jersey category names are disjoint, so these
               branches need no region guard. Dropping the guard is what closes
               the old NULL hole: a category that passed the allowlist but
               matched no branch used to survive with a null category_type,
               invisible to every workbook filter but still fanning out the
               spine columns. The `category_type is not null` filter below now
               makes the allowlist and the CASE the same list. */
            case
                when b.behavior_category in ('Written Reminders', 'Big Reminders')
                then 'Corrective'
                when
                    b.behavior_category in (
                        'Accountability (Empowerment)',
                        'Accountability (Purpose, Courage)',
                        'Be Kind (Love)',
                        'Be Kind (Revolutionary Love)',
                        'Effort (Perseverance)',
                        'Effort (Pride)',
                        'Teamwork (Community)'
                    )
                then 'BEAT'
                when
                    b.behavior_category
                    in ('Corrective Behaviors', 'Tier 1 - Corrective Behaviors')
                then 'Corrective'
                when b.behavior_category = 'Tier 1 - Habits of Excellence Corrections'
                then 'Habits of Excellence'
                when
                    b.behavior_category
                    in ('Values', 'Values (5)', 'Values (10 Point Bonus)')
                then 'BEAT'
            end as category_type,

            case
                when
                    b._dbt_source_relation like '%kippmiami%'
                    and b.behavior_category != 'Earned Incentives'
                then regexp_extract(b.behavior_category, r'([\w\s]+) \(')
                when b.behavior like '%(%)'
                then regexp_extract(b.behavior, r'([\w\s]+) \(')
                else b.behavior
            end as behavior_extracted,
        from {{ ref("stg_deanslist__behavior") }} as b
        where b.behavior_date >= '{{ var("current_academic_year") - 1 }}-07-01'
    ),

    behaviors as (
        select
            bt._dbt_source_relation,
            bt._dbt_source_project,
            bt.dl_said,
            bt.school_name,
            bt.student_school_id,
            bt.behavior_date,
            bt.behavior_category,
            bt.point_value,
            bt.entry_staff,
            bt.category_type,

            w.academic_year,
            w.quarter as term,
            w.week_start_monday,
            w.week_end_sunday,
            w.date_count as days_in_session,

            /* Normalize the EXTRACTED value, not the raw one. An equality test
               written before the parenthetical-stripping regex would miss a
               'TEAMwork (Community)'-shaped name. `Values` logs TEAMwork while
               `Values (5)` and `Values (10 Point Bonus)` log Teamwork, so
               without this the same value splits into two members inside a
               single year -- and the workbook's colour map and manual sort
               only know 'Teamwork'. */
            case
                when bt.behavior_extracted = 'TEAMwork' then 'Teamwork'
                else bt.behavior_extracted
            end as behavior,
        from behaviors_typed as bt
        inner join
            {{ ref("int_people__location_crosswalk") }} as lc
            on bt.school_name = lc.location_name
        inner join
            {{ ref("int_students__calendar_week") }} as w
            on bt.behavior_date between w.week_start_monday and w.week_end_sunday
            and w._dbt_source_project = bt._dbt_source_project
            and lc.location_powerschool_school_id = w.schoolid
        where bt.category_type is not null
    ),
```

Leave `behavior_aggregation` untouched — it already selects and groups
`behavior_category`.

- [ ] **Step 2: Project the raw category and wrap the final select**

In the final `select`, add `b.behavior_category,` immediately above
`b.category_type,`. Add `co._dbt_source_project,` as the first projected column.

Then convert that final select into a CTE named `okrts_behavior` — it currently
ends
`where co.is_enrolled_week and co.academic_year >= {{ var("current_academic_year") - 1 }}`
— and append:

```sql
select * except (_dbt_source_project),
from okrts_behavior
where {{ exclude_deanslist_stopped("_dbt_source_project", "academic_year") }}
```

The exclusion goes in the OUTER select. `school_enrollment_by_week` and
`school_iep_enrollment_by_week` are window functions; filtering inside the same
block would recompute them.

- [ ] **Step 3: Add the contract entry**

In `rpt_tableau__okrts_behavior.yml`, after the `behavior` entry:

```yaml
- name: behavior_category
  data_type: string
  description:
    Raw DeansList behavior category. Lets consumers separate the three Values
    families -- `Values`, `Values (5)` and `Values (10 Point Bonus)` all map to
    category_type BEAT, but only `Values` is comparable year over year.
```

`data_type` is mandatory. Contracts are enforced on this model.

- [ ] **Step 4: Build**

```bash
uv run dbt build --project-dir \
  /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy/src/dbt/kipptaf \
  --select rpt_tableau__okrts_behavior
```

Expected: PASS. A contract error naming `behavior_category` means Step 3 was
skipped or missing `data_type`.

- [ ] **Step 5: Assert the category domain is exactly three values and no
      nulls**

Replace `<dev_schema>` with your dbt dev schema
(`zz_<username>_kipptaf_tableau`).

```sql
select category_type, count(*) as n
from `teamster-332318.<dev_schema>.rpt_tableau__okrts_behavior`
where behavior_count is not null
group by 1
order by 1;
```

Expected: exactly `BEAT`, `Corrective`, `Habits of Excellence`. **Any null row
is a failure** — it means a category reached the extract without a mapping.

- [ ] **Step 6: Assert AY2026 corrective behaviours now render**

```sql
select region, category_type, count(*) as n, sum(behavior_count) as behaviors
from `teamster-332318.<dev_schema>.rpt_tableau__okrts_behavior`
where academic_year = 2026 and category_type is not null
group by 1, 2
order by 1, 2;
```

Expected: non-zero `Corrective` for Newark, Camden and Paterson.
`Habits of Excellence` present for Newark, Camden and Paterson. No Miami rows at
all.

- [ ] **Step 7: Assert AY2025 is unchanged — blocking**

```sql
with dev as (
  select region, school, sum(total_points) as pts, sum(behavior_count) as n
  from `teamster-332318.<dev_schema>.rpt_tableau__okrts_behavior`
  where academic_year = 2025 and behavior_category = 'Values'
  group by 1, 2
),
prod as (
  select region, school, sum(total_points) as pts, sum(behavior_count) as n
  from `teamster-332318.kipptaf_tableau.rpt_tableau__okrts_behavior`
  where academic_year = 2025 and category_type = 'BEAT'
  group by 1, 2
)
select
  coalesce(dev.region, prod.region) as region,
  coalesce(dev.school, prod.school) as school,
  dev.pts as dev_pts, prod.pts as prod_pts,
  dev.n as dev_n, prod.n as prod_n
from dev
full outer join prod using (region, school)
where dev.pts is distinct from prod.pts or dev.n is distinct from prod.n
order by 1, 2;
```

Expected: **zero rows.** Filtering to `behavior_category = 'Values'` must
reproduce today's AY2025 BEAT figures exactly, per school. Any row is a
regression — stop and diagnose before continuing.

- [ ] **Step 8: Assert the unfiltered AY2025 delta matches the prediction**

```sql
with dev as (
  select region, sum(total_points) as pts
  from `teamster-332318.<dev_schema>.rpt_tableau__okrts_behavior`
  where academic_year = 2025 and category_type = 'BEAT'
  group by 1
),
prod as (
  select region, sum(total_points) as pts
  from `teamster-332318.kipptaf_tableau.rpt_tableau__okrts_behavior`
  where academic_year = 2025 and category_type = 'BEAT'
  group by 1
)
select region, prod.pts as before, dev.pts as after,
       round((dev.pts - prod.pts) / prod.pts * 100, 1) as pct_change
from dev join prod using (region)
order by 1;
```

Expected: Newark about **+8.7%**, Camden about **+6.1%**, Paterson and Miami
excluded or unchanged. A materially larger delta means the bonus categories are
fanning out beyond one row per event.

- [ ] **Step 9: Assert `Teamwork` is a single member**

```sql
select academic_year, behavior, count(*) as n
from `teamster-332318.<dev_schema>.rpt_tableau__okrts_behavior`
where lower(behavior) = 'teamwork'
group by 1, 2
order by 1, 2;
```

Expected: exactly one `behavior` value, spelled `Teamwork`, in every year. Any
`TEAMwork` row means the normalization ran before the regex.

- [ ] **Step 10: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy \
  add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__okrts_behavior.sql \
      src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__okrts_behavior.yml
git -C /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy \
  commit -m "fix(dbt): carry both NJ culture taxonomies in rpt_tableau__okrts_behavior

Derive category_type once and filter on it instead of maintaining a separate
allowlist. Add Habits of Excellence, expose the raw behavior_category, and
normalize TEAMwork.

Refs #5062"
```

---

### Task 3: Exclude Miami from `rpt_tableau__okrts_referrals` without breaking `is_week_ytd`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__okrts_referrals.sql`

**Interfaces:**

- Consumes: `exclude_deanslist_stopped` from Task 1.

**Why this task is separate and delicate.** `is_week_ytd` is computed as
`max(if(co.academic_year = <current>, co.week_number_academic_year, 0)) over (partition by co.schoolid)`
— partitioned by school **alone**, deliberately reaching across academic years
so a prior year can be cut to the current year's week number. Removing Miami's
AY2026 rows from that partition leaves only AY2025 rows, the `max` evaluates to
0, and every Miami AY2025 row flips to `is_week_ytd = false`. Row counts stay
identical, so a count-based check passes while every Miami AY2025 referral view
goes blank.

- [ ] **Step 1: Capture the current Miami AY2025 baseline**

Run this against **prod**, before any change, and keep the output:

```sql
select is_week_ytd, count(*) as n
from `teamster-332318.kipptaf_tableau.rpt_tableau__okrts_referrals`
where academic_year = 2025 and region = 'Miami'
group by 1
order by 1;
```

Record both numbers. Step 5 compares against them.

- [ ] **Step 2: Wrap the final select in a CTE**

The final select begins `select co.student_number,` and ends
`where co.academic_year >= {{ var("current_academic_year") - 1 }}`. Convert it
to a CTE named `okrts_referrals`, adding `co._dbt_source_project,` as its first
projected column. Change the preceding CTE's closing `)` to `),` so the chain is
valid.

- [ ] **Step 3: Add the outer select**

Append after the CTE:

```sql
select * except (_dbt_source_project),
from okrts_referrals
where {{ exclude_deanslist_stopped("_dbt_source_project", "academic_year") }}
```

Do **not** add the predicate to the CTE's own `where`. That is the regression
this task exists to avoid.

- [ ] **Step 4: Build**

```bash
uv run dbt build --project-dir \
  /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy/src/dbt/kipptaf \
  --select rpt_tableau__okrts_referrals
```

Expected: PASS.

- [ ] **Step 5: Assert Miami's AY2025 `is_week_ytd` distribution is unchanged —
      blocking**

```sql
select is_week_ytd, count(*) as n
from `teamster-332318.<dev_schema>.rpt_tableau__okrts_referrals`
where academic_year = 2025 and region = 'Miami'
group by 1
order by 1;
```

Expected: **identical to the Step 1 baseline, both buckets.** If `true` has
collapsed to zero, the predicate landed inside the CTE — move it to the outer
select.

- [ ] **Step 6: Assert Miami AY2026 is gone and no other region moved**

```sql
select region, academic_year, count(*) as n
from `teamster-332318.<dev_schema>.rpt_tableau__okrts_referrals`
group by 1, 2
order by 1, 2;
```

Expected: no `Miami` row for `academic_year = 2026`. Miami 2025 and every other
region-year match prod.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy \
  add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__okrts_referrals.sql
git -C /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy \
  commit -m "fix(dbt): drop Miami from AY2026 referrals without disturbing is_week_ytd

Refs #5062"
```

---

### Task 4: Add the missing exposure dependency

**Files:**

- Modify: `src/dbt/kipptaf/models/exposures/tableau.yml` (the `okrts_dashboard`
  exposure)

**Interfaces:** none — this task is independent of Tasks 1 to 3.

The workbook uses four data sources; the exposure lists three. This is a lineage
and staleness fix, not a scheduling one: the extract-refresh schedule targets
the single exposure asset and its body is one `workbooks.refresh()` REST call,
so `deps` never gated execution.

- [ ] **Step 1: Add the ref**

In the `okrts_dashboard` exposure's `depends_on`, after the
`rpt_tableau__suspension_over_time` line:

```yaml
- ref("rpt_tableau__home_instruction")
```

- [ ] **Step 2: Verify the graph parses and the edge exists**

```bash
uv run dbt parse --project-dir \
  /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy/src/dbt/kipptaf
uv run dbt ls --project-dir \
  /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy/src/dbt/kipptaf \
  --select +exposure:okrts_dashboard --resource-type model
```

Expected: the listing includes `rpt_tableau__home_instruction` alongside the
other three.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy \
  add src/dbt/kipptaf/models/exposures/tableau.yml
git -C /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy \
  commit -m "fix(dbt): add rpt_tableau__home_instruction to the okrts_dashboard exposure

Refs #5062"
```

---

### Task 5: Whole-branch validation and PR

**Files:** none modified. This task gates the PR.

**Interfaces:** consumes the output of Tasks 1 to 4.

- [ ] **Step 1: Build all three models together**

```bash
uv run dbt build --project-dir \
  /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy/src/dbt/kipptaf \
  --select rpt_tableau__okrts_behavior rpt_tableau__okrts_referrals \
           rpt_tableau__suspension_over_time
```

Naming all three is required. `rpt_tableau__okrts_behavior` is a leaf — nothing
in `src/dbt/` refs it but the exposure — so `+` would select nothing extra and
the other two would go unbuilt.

Expected: 3 models PASS.

- [ ] **Step 2: Assert extract counts track staging for the new categories**

```sql
with staging as (
  select behavior_category, count(*) as raw_rows
  from `teamster-332318.kipptaf_deanslist.stg_deanslist__behavior`
  where academic_year = 2026
    and behavior_category in (
      'Tier 1 - Corrective Behaviors',
      'Tier 1 - Habits of Excellence Corrections',
      'Values (5)', 'Values (10 Point Bonus)')
  group by 1
),
extract_rows as (
  select behavior_category, sum(behavior_count) as extract_rows
  from `teamster-332318.<dev_schema>.rpt_tableau__okrts_behavior`
  where academic_year = 2026
  group by 1
)
select s.behavior_category, s.raw_rows, e.extract_rows,
       s.raw_rows - coalesce(e.extract_rows, 0) as dropped
from staging s
left join extract_rows e using (behavior_category)
order by 1;
```

Expected: `Tier 1 - Corrective Behaviors` and
`Tier 1 - Habits of Excellence Corrections` drop only single digits.
`Values (5)` and `Values (10 Point Bonus)` drop a large share — those are
entries dated before the school year started, which the calendar-week join
removes on purpose. Comparing against zero would pass on one surviving row,
which is why this compares against staging.

- [ ] **Step 3: Assert Paterson is present with incentives populated**

```sql
select
  school,
  count(*) as rows_out,
  sum(behavior_count) as behaviors,
  sum(is_earned_progress_to_quarterly) as progress_flags
from `teamster-332318.<dev_schema>.rpt_tableau__okrts_behavior`
where academic_year = 2026 and region = 'Paterson'
group by 1
order by 1;
```

Expected: PPES and PPMS both present with non-zero `behaviors`.

- [ ] **Step 4: Lint the spec and plan**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/fix/claude-okrts-behavior-taxonomy && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/superpowers/specs/2026-08-28-okrts-behavior-taxonomy-retrofit-design.md \
  docs/superpowers/plans/2026-08-29-okrts-behavior-taxonomy-retrofit.md </dev/null
```

Expected: no markdownlint findings. Prettier formatting findings are fixed by
the pre-commit hook and can be ignored here.

- [ ] **Step 5: Open the PR**

Use `.github/pull_request_template.md` as the body. Include in it:

- `Closes #5062`
- The AY2025 invariant result from Task 2 Step 7 (zero rows)
- The Miami `is_week_ytd` baseline comparison from Task 3 Steps 1 and 5
- A **Workbook republish required** section listing: remove the 2
  `Exclude Paterson (TEMP)` data-source filters; refresh the embedded extracts
  in Desktop so `behavior_category` appears; add the `Habits of Excellence`
  member and a parallel measure on `LP - Tree Data - BEAT Points`; add the
  `behavior_category = 'Values'` filter to `EA - Behaviors - Lines`,
  `EA - Behaviors - Roster`, `EA - Behaviors - Staff`, `SO - Behaviors - Lines`,
  `SO - Behaviors - Roster` and any year-over-year view
- A note that #5063 tracks the Paterson AD group, which is not resolved by this
  PR

---

## Self-review

**Spec coverage.** Category allowlist and CASE consolidation — Task 2 Step 1.
Third `category_type` value — Task 2 Step 1, asserted Step 5. Raw
`behavior_category` — Task 2 Steps 2 and 3. Bonus categories admitted — Task 2
Step 1, delta asserted Step 8. `TEAMwork` normalization — Task 2 Step 1,
asserted Step 9. Miami exclusion by macro and var — Task 1, applied in Tasks 1,
2 and 3. `is_week_ytd` preserved — Task 3 Steps 1 and 5. Contract entry — Task 2
Step 3. Exposure — Task 4. Build selector naming all three — Task 5 Step 1.
Extract counts against staging — Task 5 Step 2. Paterson — Task 5 Step 3.
Workbook republish steps — Task 5 Step 5.

**Not covered by any task, by design:** everything under the spec's two
out-of-scope sections, and the workbook republish itself, which the dashboard
owner performs.

**Type consistency.** The macro is called
`exclude_deanslist_stopped(project_column, year_column)` in Task 1 and invoked
identically in Tasks 1, 2 and 3. The CTE names differ per model on purpose:
`suspension_days`, `okrts_behavior`, `okrts_referrals`. The
`select * except (_dbt_source_project)` outer-select shape is identical in all
three.
