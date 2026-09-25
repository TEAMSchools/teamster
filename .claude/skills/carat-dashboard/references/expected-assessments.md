# Expected Assessments tab — rebuilding the seasons

## Procedure: Rebuild the Expected Assessments seasons tab

The `Expected Assessments` tab drives the forced scaffold in
`int_tableau__college_assessment_roster_scores` — one expected row per student
per assessment, covering a current student's entire high school history, so
Tableau renders a complete progression instead of a ragged one. KIPP Forward
owns the calendar; the data team transcribes it.

Three things about that model are easy to get wrong:

- **It is long on `score_category`.** Each row carries `score` and either
  `Scale Score` or `Score Change`, matching `expected_score_category` on the
  tab. Its two consumers — `_roster` and `rpt_gsheets__college_assessments_wide`
  — join straight through. Do not re-add a union in either; that is what was
  removed.
- **The join binds `test_type`.** Until #4658 it did not, so every practice
  scaffold row collected the matching official score and the dashboard reported
  4,107 practice rows that were official scores wearing a practice label. If
  practice numbers ever look suspiciously close to official ones, check this
  binding first.
- **Only SAT binds `academic_year`.** Grades 11 and 12 both report a Winter
  season covering December and January, so an unbound SAT score would attach to
  both. Every PSAT stays unbound deliberately — PSAT NMSQT is sat in grade 11 by
  150 current students but the tab carries it at grade 10 only, and the missing
  year binding is the only reason those scores land. Binding it drops them.

**Regenerate the whole tab. Never hand-edit it.** Two failure modes, both
silent:

- `expected_admin_season_order` is a **single reverse-chronological sequence
  across all four grades**, and inserting one administration renumbers every row
  after it. Editing one block leaves the rest inconsistent and nothing errors —
  Tableau just orders the seasons wrongly.
- **A season whose months are not listed matches no scores at all.** The join
  binds month, so an omitted month orphans every score in it with no signal.

### Step 1 — read what is already there

```sql
select
  expected_admin_season_order as ord, expected_grade_level as grade,
  expected_test_type, expected_scope, expected_admin_season as season,
  expected_month_round, expected_score_type
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__expected_assessments`
where expected_region = 'Newark'
order by expected_admin_season_order, expected_score_type
```

That model **filters out `expected_admin_season = 'Not Official'`**, so it hides
42 rows the tab actually holds. Read those from the sheet itself, not from the
model, or the rebuild deletes them. They mark months where a test genuinely
happens at a grade but is deliberately not reported — 11th-grade SAT in
Aug/Sep/Oct/Nov, and 12th-grade in Mar/May/Jun. They carry no order value and
are inert to every model, so they exist only as the record of that decision.

### Step 2 — derive the historical months, and do not skip this

The tab has **no `academic_year` column**, so one row set covers every current
student's whole history. A test's month moves between years, so transcribing
only this year's calendar orphans earlier cohorts' scores:

```sql
with
  current_hs as (
    select distinct student_number
    from `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments`
    where academic_year = {{ current year }} and school_level = 'HS'
      and rn_year = 1 and not is_out_of_district
  )
select
  h.scope, h.test_type, format_date('%B', h.test_date) as test_month,
  count(distinct h.student_number) as current_students
from `teamster-332318.kipptaf_assessments.int_assessments__all_college_assessments` as h
inner join current_hs as c on h.student_number = c.student_number
where h.test_date is not null
group by h.scope, h.test_type, test_month
order by h.scope, h.test_type, current_students desc
```

Measured 2026-08: PSAT 8/9 October (785 current students), PSAT NMSQT October
(336), PSAT10 April (416) and March (8). PSAT10's official month has moved
February to March to April across four years. So a rebuild that puts G9 and G10
official in March alone orphans roughly 1,500 students' PSAT scores.

Scope the query to **currently enrolled** students, which self-prunes months
only reachable by graduates. A season is defined by the month a score actually
landed in, not by this year's plan, so a test with a moved calendar needs
**both** months — possibly as two seasons, the way SAT already carries G11
Winter as December _and_ March.

### Step 3 — take the dates, infer the season, ask only when you cannot

Ask KIPP Forward for administration **dates** per grade and test type. Do not
ask for season labels up front — derive them from what the tab already encodes:

```sql
select
  expected_grade_level as grade, expected_scope as scope,
  expected_test_type as tt, expected_month_round as month,
  expected_admin_season as season
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__expected_assessments`
where expected_region = 'Newark' and expected_grouping = 'Total'
group by grade, scope, tt, month, season
order by grade, scope, season, month
```

Resolve each date in this order, and say which rule fired:

1. **Same grade, scope and test type already maps that month** — use that
   season. The only case needing no confirmation.
2. **Same scope at another grade maps it** — propose it, and say it came from a
   different grade.
3. **Neither** — ask. Never fall back to a calendar convention silently.

Two cases where rule 1 will not save you. **March is mapped to Winter at grade
11 and to Spring at grade 9**, so a March date always needs asking. And as of
2026-08 the PSAT grades map only `Year`, so no PSAT month has a precedent at all
— every PSAT season needs asking until the first rebuild lands.

Present the historical months from step 2 alongside their answer and **require
an explicit decision to drop a month**. Dropping by omission is the failure this
procedure exists to prevent.

### Step 4 — generate every row

Write the year's spec in the session scratchpad, not the repo: the live tab is
the record, and a committed copy goes stale every year. Start from
[`scripts/expected_assessments_spec.example.json`](../scripts/expected_assessments_spec.example.json),
which shows each kind of entry once (a practice round, an official test with and
without growth, and a `not_reported` block), and fill it from the calendar
confirmed in step 3. Then run
[`scripts/build_expected_assessment_rows.py`](../scripts/build_expected_assessment_rows.py):

```bash
uv run python .claude/skills/carat-dashboard/scripts/build_expected_assessment_rows.py \
    <scratchpad>/spec.json <scratchpad>/out.tsv
```

It computes the order sequence, emits one row per score type per month, emits a
single growth row per administration carrying the **season name** in
`expected_month_round` rather than a month, and rejects a spec where a month
belongs to two seasons of the same test and grade, or where an administration
has no months.

Verified against the live tab: it reproduces all 110 existing SAT rows exactly,
order values included.

**`expected_month_round` is polymorphic, deliberately.** It holds a month on an
Official row, the `scope_round` on a Practice row (`SAT1`, `PSAT891`,
`PSAT101`), and the season name on a growth row. Practice cannot bind on month:
schools choose their own practice dates, so one administration straddles months
— grade 9 runs 25 August to 23 September across four schools — and Foundation
controls the Illuminate dates, so they cannot be normalised either.
`scope_round` identifies the administration regardless of when a school ran it.

Three consequences. `expected_months_included` reads `SAT1` rather than months
for practice, since it aggregates the same column. Two practice administrations
may share a month without ambiguity, which matters because grade 11's SAT2 may
also fall in September. And the score side needs a matching key,
`if(test_type = 'Practice', scope_round, format_date('%B', test_date))`, which
means **`scope_round` has to reach `int_assessments__all_college_assessments`**.
It does, as `aligned_month_round` — the hub unions `test_month` on official rows
and `scope_round` on practice rows under that one column, so a consumer joins
the tab without knowing which pipeline a row came from. `administration_round`
is no substitute, being null on every externally created assessment and wrong on
the one that has it (`Jul 23` against September test dates).

**A growth row needs its score type to exist.** Only `sat_total_score_growth` is
in the scaffold and hub vocabulary today, so `"growth": true` on a PSAT
administration emits `psat89_total_growth` and friends, which nothing downstream
knows. Adding growth to PSAT means adding those score types to the scaffold
first — see the roster-scores growth work in TODO(#4658). Leave
`"growth": false` on PSAT until then.

Eight columns, no header, paste over **A2** of `Expected Assessments`:

`expected_region`, `expected_grade_level`, `expected_test_type`,
`expected_scope`, `expected_score_type`, `expected_month_round`,
`expected_admin_season`, `expected_admin_season_order`.

### Step 5 — audit the paste before trusting it

Rebuild the staging model into a dev schema first
(`dbt build --select stg_google_sheets__kippfwd__expected_assessments --target dev`)
— a Sheets external reads live, so a value edit needs no re-stage, but the
`stg_` table is a table and will serve pre-paste content until it rebuilds.

Then run all five checks. Each one catches a different way the paste goes wrong,
and four of them fail silently in the report rather than erroring.

**A — shape and symmetry.** A truncated paste shows up here and nowhere else.

```sql
select
  expected_region,
  count(*) as n_rows,
  count(distinct expected_admin_season_order) as distinct_orders,
  min(expected_admin_season_order) as min_ord,
  max(expected_admin_season_order) as max_ord,
  countif(expected_admin_season_order is null) as null_orders
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__expected_assessments`
group by expected_region
order by expected_region
```

Both regions must be identical on every column, `min_ord` must be 1, and
`null_orders` must be 0 — the model already filters `Not Official`, so a null
order here means a reported row lost its order value.

**B — one order per administration.** Every month row of one administration
shares a single order value. More than one means the paste mixed two blocks.

```sql
select
  expected_grade_level, expected_test_type, expected_scope,
  expected_score_type, expected_admin_season,
  count(distinct expected_admin_season_order) as n_orders
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__expected_assessments`
group by 1, 2, 3, 4, 5
having count(distinct expected_admin_season_order) > 1
```

**C — a month in two seasons.** This one fans out scores rather than dropping
them, so it inflates a count instead of shrinking it. Growth rows are excluded
because they carry the season name where a month would go.

```sql
select
  expected_grade_level, expected_test_type, expected_scope, expected_month_round,
  string_agg(distinct expected_admin_season order by expected_admin_season) as seasons
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__expected_assessments`
where expected_grouping != 'Growth'
group by 1, 2, 3, 4
having count(distinct expected_admin_season) > 1
```

**D — the admin id still identifies one administration.**
`expected_unique_test_admin_id` hashes test type, aligned score type, grade and
season, and `int_tableau__college_assessment_roster_scores` joins on it. Two
administrations sharing a hash silently merge their scores.

```sql
select
  expected_unique_test_admin_id,
  expected_score_category,
  count(distinct expected_admin_season_order) as n_orders,
  string_agg(distinct expected_score_type order by expected_score_type) as score_types
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__expected_assessments`
group by 1, 2
having count(distinct expected_admin_season_order) > 1
```

**`expected_score_category` has to be in that group by.** A growth row hashes to
the same id as its own Total row on purpose — `expected_score_type_aligned` maps
`sat_total_score_growth` to `sat_total_score` — and the two are separated by
score category, which is the other half of the join key in
`rpt_tableau__college_assessment_dashboard_roster`. Grouping on the id alone
flags every growth pair as a collision; that false positive shipped in this
procedure once.

Region is deliberately absent from that hash, so both regions share ids. That is
fine — a student belongs to one region and the enrollment join constrains it
before the hash join runs.

**E — nothing orphaned.** The check that catches a missing month:

```sql
with
  scores as (
    select
      h.scope, h.test_type, h.aligned_month_round,
      count(distinct h.student_number) as students
    from `teamster-332318.kipptaf_assessments.int_assessments__all_college_assessments` as h
    where h.aligned_month_round is not null
    group by h.scope, h.test_type, h.aligned_month_round
  )
select
  s.scope, s.test_type, s.aligned_month_round, s.students,
  if(s.scope = 'ACT', 'ACT never on this sheet', 'ORPHAN') as verdict
from scores as s
left join
  `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__expected_assessments` as a
  on s.scope = a.expected_scope
  and s.test_type = a.expected_test_type
  and s.aligned_month_round = a.expected_month_round
where a.expected_scope is null
order by s.students desc
```

`aligned_month_round` on the hub is what lets one join serve both pipelines — it
holds the month on an official row and the `scope_round` on a practice row,
matching the tab's own polymorphic column.

**Triage before acting.** Measured 2026-08 against the rebuilt tab, this returns
13 rows and only one is a genuine gap:

- **ACT is 12 of the 13**, about 4,240 students. `_roster_scores` has never
  covered the ACT and the sheet holds no ACT rows, so these are a standing scope
  gap rather than anything a rebuild caused. Keep them labelled rather than
  filtered out, or a future decision to add the ACT will look like it already
  works.
- **SAT Official July, 1 student** — the only real orphan, and immaterial.

Two groups used to appear here and no longer do. Their return would mean
something, so they are worth knowing: **SAT Official January** held 334 students
before January was added to Winter at grades 11 and 12, and **practice scores**
orphaned wholesale while the join still matched on month. The seeded practice
set is dated 2026-08-19 against a September administration and matches `SAT1`
regardless, which is the whole point of round binding.

Cross-check anything else against the `Not Official` list before adding it — it
may be a deliberate exclusion rather than a gap.

**The `Not Official` rows are invisible to all five checks**, because the
staging model filters them out. Count them on the sheet itself; the SY26-27 tab
carries 42. A paste that dropped them looks perfectly healthy here.
