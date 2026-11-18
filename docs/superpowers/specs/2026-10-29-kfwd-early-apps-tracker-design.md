# KIPP Forward early apps tracker: design

Issue: [#6190](https://github.com/TEAMSchools/teamster/issues/6190)

## Intent

KIPP Forward counselors and school leaders track whether seniors who plan to
apply early (Early Action, EA, or Early Decision, ED) are meeting the
early-application goals set for their GPA band. Today the tracker is a one-time
spreadsheet built from 2 Overgrad exports. A student who submits after an export
never appears, and a stakeholder found 2 seniors with GPAs above 3.75 and
submitted ED applications missing for exactly that reason.

The goal is a Google Sheet that refreshes every day from Overgrad data in
BigQuery, so stakeholders always see who is on track, who has not submitted yet,
and who just missed a goal. Counselors use it to decide which seniors to follow
up with before early deadlines.

## Goals

- A Reports sheet with 4 tabs: Summary, Roster, Not Submitted Yet, Near Misses.
- Data refreshes daily with no manual export.
- Every rule lives in dbt, so a rule change is one code change.
- The sheet rolls to the next senior class each July without edits.

## Non-goals

- "Meets full need" as a real college attribute. It stays a placeholder that
  treats every college as meeting full need, until the source is cleaned up.
- Near misses on GPA (for example a 3.73 just under the 3.75 bar).
- Counting `Will Apply` applications toward any criterion.
- Changing the Tableau KIPP Forward Data Suite. A separate Tableau sheet with
  these criteria on Salesforce data exists only as a review copy.

## Anti-goals

- A tracker that disagrees with Overgrad for longer than one refresh. That is
  the failure being fixed.
- Rule logic in spreadsheet formulas. The report sheet uses `IMPORTRANGE` only
  (`docs/guides/google-sheets.md`).
- Stakeholders holding the source sheet link, where an edit can break the
  refresh for everyone.

## Constraints

- **Two-sheet publishing.** Per `docs/guides/google-sheets.md`: a source sheet
  in the Data Integration shared drive's IMPORTRANGE Sources folder, named
  exactly after the model, holds the Connected Sheets extracts and the refresh
  schedule. A Reports sheet with friendly tab names pulls each tab with
  `IMPORTRANGE`. The exposure `url` points at the source sheet.
- **Layering.** Rule A1 in `.claude/rules/dbt-architecture.md`: an `rpt_` reads
  marts and domain `int_` models only. `rpt_gsheets__overgrad_award_letter`
  reads Overgrad staging directly, but that edge is a baselined exception
  (`src/dbt/kipptaf/standard-baseline.tsv`, #5811) and must not be copied. The
  per-student logic goes in a domain `int_` (folders listed in `DOMAIN_FOLDERS`,
  `scripts/check_dbt_standard.py`).
- **PII.** The roster, not-submitted, and near-miss models carry student names,
  GPAs, and application status. Tag them `contains_pii` per
  `.claude/rules/ferpa-pii.md`. The Summary model is aggregate only.
- **Naming.** New KIPP Forward Google Sheets extracts use the
  `rpt_gsheets__kfwd_` prefix (`src/dbt/kipptaf/CLAUDE.md`).

## Approaches

- **A. dbt models feeding the two-sheet Connected Sheets setup. Chosen.** All
  rules live in reviewed, tested SQL, and a counselor cannot break the tracker
  by editing it. It costs a code review and about 30 minutes of manual sheet
  setup, and every later column change must be made in both sheets.
- **B. Connected Sheets on the raw Overgrad tables with the rules as sheet
  formulas.** It could go live the same day. It was rejected because the
  near-miss and "additional school" rules would be long, untested formulas that
  break when someone sorts or inserts a column, and because it violates the
  team's no-logic-in-report-sheets rule.
- **Dropped:** the Tableau sheet as the tracker (stakeholders want a Google
  Sheet, and it reads Salesforce, not Overgrad), and a Dagster asset that writes
  rows into the sheet (no such pattern exists; published sheets read BigQuery
  through Connected Sheets).

## Decisions

### Source

Overgrad directly, not Salesforce. Overgrad syncs to Salesforce about 1 day
behind, and the stakeholder wants the freshest data. The Tableau dashboards read
Salesforce, so on a given day the tracker may be 1 day ahead of them.

### Population (N)

- Current seniors: Overgrad `int_overgrad__students.graduation_year` =
  `var("current_academic_year") + 1`.
- High schools: KIPP Cooper Norcross High School, KIPP Newark Collegiate
  Academy, KIPP Newark Lab High School (`school__name`). The Overgrad "MS
  Completers" schools are excluded.
- **N = seniors whose student-level custom field `is_ed_ea` = `Yes`.** On
  2026-10-29 that was 130 seniors.
- GPA = `academics__unweighted_gpa`. Bands: 3.75+, 3.50-3.74, 3.00-3.49, below
  3.00. A flagged senior below 3.00, or with no GPA, is in N and shows `N/A` for
  every criterion.
- Counselor = `assigned_counselor__first_name` and
  `assigned_counselor__last_name`.

### Applications

From `int_overgrad__admissions`, joined to the student on `student__id` and
`_dbt_source_project`. Both models union regions, and ids can repeat across
regions (rule A10).

- **Counts are distinct colleges** (`university__id`), not admission rows, so a
  duplicate row can never turn a No into a Yes. On 2026-10-29 no current senior
  had 2 submitted early rows for one college.
- **GPA band** uses `round(academics__unweighted_gpa, 2)`, matching the KIPP
  Forward Tableau logic. Overgrad stores 2 decimals or fewer today, so the
  rounding changes nothing now.

- **Early:** `due_date__type` in `early_action`, `early_action_2`,
  `early_decision`, `early_decision_2`, `single_choice_early_action`. `regular`,
  `priority`, and null are not early.
- **ED:** `early_decision`, `early_decision_2`. **EA:** `early_action`,
  `early_action_2`, `single_choice_early_action`.
- **Submitted:** `status` in `Applied`, `Accepted`, `Denied`, `Deferred`,
  `Waitlisted`, `Enrolled`. Not submitted: `Will Apply`, `Withdrew`,
  `Did Not Apply`.
- The admissions-level custom field `is_ed_ea` is blank on every current-senior
  row. Do not use it.

### URM graduation rate

Overgrad does not carry graduation rates. Use
`stg_kippadb__account.adjusted_6_year_minority_graduation_rate`, joined on
`stg_kippadb__account.nces_id` =
`cast(int_overgrad__admissions.university__ipeds_id as string)`. This is the
rate the Tableau dashboards use. On 2026-10-29 it matched 986 of 991
current-senior early applications, with no IPEDS id on more than 1 account. An
application with no rate never counts toward a URM bar and is never a near miss.

### Criteria

Each criterion applies only to its GPA band. Every count uses submitted early
applications only.

| Band      | Criterion                    | Rule                                                                                  |
| --------- | ---------------------------- | ------------------------------------------------------------------------------------- |
| 3.75+     | 1 ED, full need, 80%+ URM    | At least 1 submitted ED application with URM >= 80 at a full-need college             |
| 3.75+     | 2 EA, 78%+ URM               | At least 2 submitted EA applications with URM >= 78                                   |
| 3.75+     | Met both                     | Both rows above                                                                       |
| 3.50-3.74 | 1 ED/EA, full need, 80%+ URM | At least 1 submitted early application with URM >= 80 at a full-need college          |
| 3.50-3.74 | 2 additional early, 68%+ URM | (Submitted early applications with URM >= 68) minus min(full-need 80%+ count, 1) >= 2 |
| 3.50-3.74 | Met both                     | Both rows above                                                                       |
| 3.00-3.49 | 3 early, 68%+ URM            | At least 3 submitted early applications with URM >= 68                                |

"Additional" means the 1 full-need school that satisfies the first 3.50-3.74 row
is not counted again. A second full-need school does count as additional.

**Full need placeholder:** every college counts as meeting full need. Keep it a
single named column (for example `is_full_need`, always true) so that replacing
it later is a one-line change.

### Near misses

The tab has 2 jobs: find seniors who could still meet a goal with a small
change, and show a counselor why a senior they believed met a goal did not count
(for example, the ED college is 3 points under the URM bar).

Only for the senior's own band, only where the criterion is No, and only from
submitted applications.

A **near-bar college** is a submitted application of the type the rule needs
with URM within 5 points under the bar: 75 to under 80 for the 80% rules, 73 to
under 78 for the 78% rule, 63 to under 68 for the 68% rules. For the 3.75+ ED
rule only ED applications count; for the 3.75+ EA rule only EA applications
count.

- **1-school rules** (3.75+ ED 80%+, 3.50-3.74 full-need 80%+): a near miss when
  the senior has at least 1 near-bar college. A 3.75+ senior with no ED
  application at all is a plain No, not a near miss.
- **2- and 3-school rules** (2 EA 78%+, 2 additional 68%+, 3 early 68%+): a near
  miss when either is true:
  - the senior is exactly 1 qualifying college short, or
  - qualifying colleges plus near-bar colleges reach the required number, so
    raising the near-bar colleges to the bar would close the gap. A senior with
    0 qualifying colleges and 1 near-bar college on the 3-school rule is not a
    near miss.
- For the 2 additional 68%+ rule, "qualifying" means qualifying additional
  colleges, after the 1 full-need college is set aside.
- Each criterion appears once per senior. "What they have" lists the qualifying
  and near-bar colleges with their URM rates.

### Tabs

**Summary.** Rows: N, the band counts (3.75+, 3.50-3.74, 3.00-3.49, below 3.00),
then 2 rows per criterion: "% of N" and "% of band". Columns: Cooper Norcross,
Newark Collegiate, Newark Lab, All. Each cell is text like `3% (1/40)`: the
percent rounded to a whole number, then met and the denominator. The denominator
is N for "% of N" rows and the band count for "% of band" rows. A band with 0
seniors shows `-`. The model also carries numeric columns (met, denominator,
percent) for each cell, placed to the right in the sheet, for anyone who wants
to chart them.

**Roster.** 1 row per senior in N. Columns: student, high school, counselor,
GPA, GPA band, met all criteria for the band (Yes, No, N/A), count of submitted
early applications, then for each criterion a Yes/No/N/A column and a column
listing the qualifying colleges (comma-separated, alphabetical, filled only when
Yes), then a count of near misses, then every submitted early application with
its type and URM rate (for example "Example College (ED) 77%"). The last column
answers "why didn't this senior count?" even when a college is more than 5
points under the bar and so never reaches the Near Misses tab.

**Not Submitted Yet.** 2 sections, told apart by a `section` column.

- A. Seniors in N with no submitted early application. Columns: student, high
  school, counselor, GPA band, early applications on their list with status
  `Will Apply` (college and type, comma-separated), and the earliest
  `due_date__date` among them. Seniors with none on their list show a blank
  list.
- B. Current seniors at the 3 schools who have at least 1 submitted early
  application but whose `is_ed_ea` is not `Yes`. Columns: student, high school,
  counselor, GPA band, submitted early applications. The sheet labels this
  section "Fix the Is ED/EA flag in Overgrad". These seniors are outside N.

**Near Misses.** 1 row per senior per missed criterion. Columns: student, high
school, counselor, GPA band, criterion, what they have (for example "Example
College (ED) at 78.2%"), what would close it (for example "An ED college at
80%+, 1.8 points short", or "1 more EA college at 78%+").

### Refresh

Connected Sheets refreshes every tab in the source sheet daily, after the
Overgrad and dbt runs complete. The Summary tab shows a "data as of" date taken
from the data, not the refresh clock.

## Left to the builder

- Model names, the domain folder for the per-student `int_`, and how the logic
  splits between models, within rules A1 to A11.
- Whether the Summary text cells are built by unpivoting or by explicit union.
- The source of the "data as of" date (for example the latest Overgrad
  `updated_at` in scope).
- Uniqueness tests at each model's grain and the exposure entry in
  `src/dbt/kipptaf/models/exposures/google-sheets.yml`.
- Step-by-step setup notes for the 2 sheets in the PR, for the person who
  creates them.

## How to check it

- N matches a direct count of current seniors at the 3 schools with `is_ed_ea` =
  `Yes`.
- The 2 seniors from the 2026-10-29 stakeholder report behave as follows. Their
  names are in the build session's conversation; look them up in the terminal
  only, and never write them to git, the PR, or the issue. The senior with a
  submitted ED application at 80%+ and 2 submitted EA applications at 78%+ shows
  Yes on both 3.75+ criteria. The senior with a submitted ED application at
  78.2% and 1 submitted EA application at 78%+ shows No on both 3.75+ criteria
  and 2 near-miss rows.
- Summary cells add up: met and denominators per school sum to the All column.
