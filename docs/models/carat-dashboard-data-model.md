# CARAT Dashboard Data Model

How the College Admission Readiness Assessments Tracker (CARAT) works: where its
data comes from, how the dbt models turn it into the dashboard, what each view
shows, and what to know before changing any of it.

## What is CARAT?

CARAT is KIPP Forward's dashboard for college-entrance testing: SAT, PSAT 8/9,
PSAT 10, PSAT NMSQT, historical ACT, and AP. KIPP Forward is the KTAF team that
supports students' paths to and through college. For current high school
students and past graduating classes, CARAT reports how many students tested,
what they scored, how many reached readiness benchmarks, and how the network is
tracking against the goals KIPP Forward sets each year.

It reports two kinds of results side by side:

- **Official** scores are real College Board and ACT results.
- **Practice** scores come from practice tests students take in school, recorded
  in Illuminate and converted to the official scale.

The Tableau workbook is declared in dbt as the exposure
`college_admission_readiness_assessments_tracker_carat`, and Dagster refreshes
its extracts daily at 6 AM Eastern. The data team maintains it with two Claude
Code skills: `carat-dashboard` for the dashboard's pipeline and
`collegeboard-id-crosswalk` for matching College Board score files to students.
The skills hold the step-by-step procedures; this page explains the model.

## How it fits together

```text
 Official                               Practice
 kippadb: SAT, ACT                      Illuminate responses
 College Board files: PSAT             + Scale Score Conversion tab
   (matched to students by the          + Scaffold tab
    College Board ID crosswalk)           │
   │                                      │
   ▼                                      ▼
 official model                          practice model
 int_assessments__college_assessment     int_assessments__college_assessment_practice
   └──────────────────┬───────────────────┘
                      ▼
      the hub: int_assessments__all_college_assessments
                      │
   ┌──────────┬───────┴───────┬───────────────┬─────────────────────┐
   ▼          ▼               ▼               ▼                     ▼
 _scores   _current      _over_time     _benchmark_calcs     roster scores ─► _roster
              ▲               ▲                                     ▲
              └─── goals ─────┘                                     └── Expected Assessments tab
```

Official and practice results stay in separate models until the hub, which
unions them into one shape. From there down, `test_type` (`Official` or
`Practice`) is what tells them apart. Enrollment data (school, grade, graduation
year) joins in at each view from `int_extracts__student_enrollments`.

Not everything reads the hub. `_roster` also reads the official model directly
for SAT highlights, and the wide KIPP Forward sheet reads some College Board and
kippadb models directly. Two views sit outside this pipeline entirely: `_de`
reads PowerSchool grades, and AP has its own path (see _Dashboard views_).

## Terms

| Term                     | Meaning                                                                                              |
| ------------------------ | ---------------------------------------------------------------------------------------------------- |
| `_scores`, `_current`, … | Short names for the views `rpt_tableau__college_assessment_dashboard_scores`, `…_current`, and so on |
| kippadb                  | The network's Salesforce instance, where official SAT and ACT scores are recorded                    |
| Official model           | `int_assessments__college_assessment`: official scores                                               |
| Practice model           | `int_assessments__college_assessment_practice`: practice scores                                      |
| The hub                  | `int_assessments__all_college_assessments`: both, unioned                                            |
| `scope`                  | The test: `SAT`, `ACT`, `PSAT 8/9`, `PSAT10`, `PSAT NMSQT`                                           |
| `score_type`             | One score on one test: `sat_total_score`, `sat_math`, `psat89_ebrw`, …                               |
| `scope_round`            | Which practice administration within a year: `SAT1`, `SAT2`, `PSAT891`, `PSAT101`                    |
| `rn_highest`             | A score's rank among the student's scores of that type; 1 is their best                              |
| Superscore               | A student's best section scores across sittings, summed                                              |
| `rn_year`                | `1` on a student's primary enrollment row for a year; views filter on it for one row per student     |
| IEP-exempt               | Students exempt from the graduation assessment requirement under their IEP                           |

## Where the data comes from

| Source                            | What it provides                                      | Owner                                  |
| --------------------------------- | ----------------------------------------------------- | -------------------------------------- |
| kippadb (Salesforce)              | Official SAT and ACT scores                           | KIPP Forward                           |
| College Board files, via SFTP     | Official PSAT and AP scores                           | College Board                          |
| College Board ID crosswalk sheets | Each College Board ID's PowerSchool `student_number`  | Data team                              |
| Illuminate                        | Practice test responses (raw scores)                  | Schools and KIPP Forward               |
| KIPP Forward workbook (four tabs) | Practice conversions, test vocabulary, goals, seasons | KIPP Forward, entered by the data team |
| PowerSchool, via enrollments      | Student, school, grade, graduation year               | Schools                                |

The four KIPP Forward tabs are described under _The Google Sheets_. Edits to
them reach the warehouse on their own: a Dagster sensor watches the workbook's
modified time and rebuilds the staging models, usually within an hour of an
edit. Tableau shows the change after its next daily refresh.

### How official SAT reaches the dashboard

College Board also sends SAT files, but CARAT never reads them. Official SAT on
the dashboard comes from kippadb only. The files reach kippadb by a round trip
the data team runs:

1. The SAT files land and are matched to students through the SAT/PSAT crosswalk
   (`int_collegeboard__sat_unpivot`).
2. Two extracts, `rpt_gsheets__kippfwd_sfsat` and `rpt_gsheets__kippfwd_ogsat`,
   list every College Board SAT score that kippadb doesn't have yet, matching on
   student, score type, and exact test date. They feed the Unified KFWD
   Processes Document, a Google Sheet.
3. The data team loads those rows into Salesforce. Once a score is in kippadb it
   drops off the sheet, and it reaches CARAT through the official model.

So for years with College Board files, which start in spring 2022 and are nearly
complete from school year 2024-25, kippadb and the College Board tables should
agree score for score. A score still on the sheet hasn't been loaded yet.

kippadb also holds SAT scores with no College Board record: sittings before the
files began, sittings whose reports never came to the school, and scores entered
by hand. Scores entered by hand, including by the KIPP Foundation, have been
wrong before. When someone asks why CARAT disagrees with a College Board report,
compare the two sources first (the `carat-dashboard` skill has the query). A
score in both with different values, or a College Board score that isn't in
kippadb on the same date, points to a Salesforce entry. A different date is
enough to break the match.

## Key ideas

### `test_type` and `scope`

Every score row carries two labels: `test_type` (`Official` or `Practice`) and
`scope` (the test). Anything selecting a specific test reads `scope`.
`test_type` is constant within the official and practice models, so a predicate
like `test_type = 'SAT'` is never true and fails silently.

### Official and practice share one vocabulary

A `score_type` is spelled the same way for official and practice results. That
keeps the views simple, but it means the same `score_type` names a different
sitting depending on `test_type`. **Rankings, deduplication, and joins carry
`test_type`**, so a practice score can never outrank, replace, or be counted as
an official one. When adding a `partition by` or a join, include `test_type`
unless the calculation is meant to span both.

Two calculations are meant to span both, and leave `test_type` out on purpose:
the roster's growth (see _Growth_) and the hub's `previous_score_change`.

### Attempts

An attempt is one sitting of a test, recorded on the total row. The hub counts
attempts as distinct test dates per student, test type, and score type:
`attempt_lifetime` across all years and `yearly_attempts_totals` per year.
Counting rows instead would credit a sitting entered twice in kippadb as two
attempts.

The attempts metrics ask what share of students took a test at least once, or at
least twice. On the dashboard, **every metric's denominator is every student in
the group, whether or not they tested**: the workbook filters `_current` to
currently enrolled students who aren't IEP-exempt, then divides the students who
met the bar (`met_min_score_int = 1`) by all rows. A student with no score has
`met_min_score_int = 0`, so they count as not meeting it. Checked against the
published Landing Page, where every bar's count matches this calculation.

Attempt counts are lifetime: "1+ attempts" means the student has ever sat the
test, in any year, so a grade's rate climbs through the year as its first
official sitting arrives (grade 11 SAT reads near zero in the fall).

`score` itself reads 0 on an Attempts row for a student who holds results of
that test type but never sat this test, and null for a student with no results
of that type. That distinction matters only when averaging `score`; the
percentages don't depend on it.

### Benchmarks

Benchmarks are two score thresholds per test, set by KIPP Forward: **HS
Grad-Ready**, the New Jersey graduation bar, and **College-Ready**.

| Test            | Score          | HS Grad-Ready | College-Ready |
| --------------- | -------------- | ------------- | ------------- |
| SAT             | Total          | 890           | 1010          |
| SAT             | EBRW / Math    | 450 / 440     | 480 / 530     |
| PSAT 10 / NMSQT | Total          | 840           | 910           |
| PSAT 10 / NMSQT | EBRW / Math    | 420 / 420     | 430 / 480     |
| PSAT 8/9        | Total          | 790           | 860           |
| PSAT 8/9        | EBRW / Math    | 400 / 400     | 410 / 450     |
| ACT             | Composite      | 17            | 21            |
| ACT             | Math / Reading | 17            | 22            |

The thresholds live on the Scaffold tab, not in SQL. Four score types have no
thresholds, by design: `act_english`, `act_science`, `sat_reading_test_score`,
and `sat_writing_and_language_test_score`.

Benchmark results combine tests in two ways:

- **PSAT 10 and PSAT NMSQT fold together for scores.** College Board treats them
  as one test offered in two windows, on a compatible scale, so a student's best
  is taken across both (`benchmark_aligned_scope`).
- **ACT and SAT fold together for attainment only**: "met the bar by any route"
  (`expected_aligned_scope = 'ACT/SAT'`). Their scores are never compared, since
  ACT Math is 1-36 and SAT Math is 200-800.

The two columns look alike and are not interchangeable. A max score taken across
`ACT/SAT` would rate an ACT 36 against a 1010 threshold.

### Goals

KIPP Forward sets goals as the percent of students meeting each metric, per
graduating class: one attempt, two or more attempts, HS Grad-Ready, and
College-Ready. They are entered on the Goals tab.

- **Goals don't vary by region or school.** Every school shows the same goal
  line for a given grade and metric.
- **Grade pairs one-to-one with graduating class** within a year. In SY26-27,
  grade 12 is the class of 2027 and grade 11 the class of 2028, so the two SAT
  goal rows are goals for two classes.
- **The Goals tab holds percentages only**; thresholds come from the Scaffold
  tab. `int_google_sheets__kippfwd__goals_unpivot` pairs them.

The topline table below is KIPP Forward's strategy target per class, by the end
of junior year. The Goals tab doesn't hold it as-is: the tab has one row per
current grade and test for this school year, so a class's SAT goal appears on
the tab only while that class is in grade 11 or 12. In SY26-27 the class of 2029
is in grade 10, so its only row is PSAT 10.

Topline goals, by the end of junior year:

| Class of | College-Ready (1010+) | HS Grad-Ready (890+) |
| -------- | --------------------- | -------------------- |
| 2027     | 22%                   | 45%                  |
| 2028     | 28%                   | 55%                  |
| 2029     | 34%                   | 60%                  |
| 2030     | 40%                   | 70%                  |
| 2031     | 47%                   | 80%                  |

Attempts goals are 95% for one attempt on every PSAT and the SAT, and 95% for
two or more attempts on the SAT, official and practice. PSAT has no two-or-more
goal because it is given once a year.

`_over_time` reports on neither grade nor class, so it needs one goal per
metric. The Goals tab carries two columns for it, `pct_hs_grad_ready_over_time`
and `pct_college_ready_over_time`. **Their values are placeholders** that hold
the dashboard's goal lines steady until KIPP Forward states a goal that doesn't
depend on class. Don't reconcile them against the topline table.

### Seasons and the Expected Assessments tab

The roster shows each student's progression across the tests they are expected
to take in high school. The Expected Assessments tab defines those
administrations: for each region, grade, and test, the season (Fall, Winter,
Spring) and the months that belong to it. An official score lands in a season by
matching its month; a score from a month the tab doesn't list has nowhere to go.

Practice tests match on their round instead. Schools choose their own practice
dates, so one practice administration can span several months; practice rows on
the tab list the `scope_round` where official rows list a month.

Months marked `Not Official` record tests that happen but are deliberately not
reported, such as grade 11 SAT in the fall. Seasons are ordered by one sequence
across all grades, so the tab is regenerated whole, never edited by hand; the
`carat-dashboard` skill has the generator and an example spec.

### Growth

The roster's growth rows (`Score Change`) measure the change from a student's
previous season, in the order the tab defines. The chain runs through official
and practice administrations alike: an official grade 11 Winter change is
measured from practice SAT1 when the student sat it, and a practice SAT2 change
is measured from an official Winter sitting when there is one. Growth is
computed for SAT totals only; the model restricts it to them.

For official-to-official growth, use `previous_total_score_change` on the
official model (the change from the previous official sitting of the same test)
or the official-only growth columns on the wide KIPP Forward sheet. Splitting
the roster's growth by test type would mean adding `test_type` to its partition;
confirm with KIPP Forward before changing it.

### Two graduating-class fields

`int_extracts__student_enrollments` carries both `graduation_year` and
`ktc_cohort`, and they differ for a few percent of students, such as a retained
student. **Both are correct**: KIPP Forward uses one and the KIPP Foundation the
other. `_benchmark_calcs` carries `graduation_year` and drops students without
one; the other views carry both. Don't unify them. A goal should say which basis
it is measured on.

## Dashboard views

The published workbook has five tabs. Each view feeds one of them:

| Tab          | What's on it                                                       | View                                   |
| ------------ | ------------------------------------------------------------------ | -------------------------------------- |
| Landing Page | Average scores by graduating class (left)                          | `_scores`                              |
| Landing Page | Grades 11 and 12 against goal, by school, region, and NJ (right)   | `_current`                             |
| Over Time    | Attainment by graduating class                                     | `_over_time`                           |
| Roster       | Each current student's expected tests and scores (the default tab) | `_roster`                              |
| AP Overview  | AP enrollment, attempts, and scores                                | `rpt_tableau__ap_assessment_dashboard` |
| DE Overview  | Dual-enrollment results                                            | `_de`                                  |

`_benchmark_calcs` has no tab of its own. The Landing Page's "Met Benchmark" and
"CY Board Report" buttons open pop-ups, and the benchmark view most likely sits
behind the first; confirm in Tableau before relying on that.

### `_scores`: average scores

**What it shows:** the landing page. Average scores over time by graduating
class; rows are `test_type` then `graduation_year`, columns are the tests. The
Score Category filter switches between each sitting's own score (`scale_score`)
and the student's best (`max_scale_score`).

**Grain:** one row per student, test type, score type, test date, and score,
official and practice. Reads the hub and enrollments.

**Worth knowing:**

- Both Score Category options average over every sitting, so a student who
  tested twice counts twice either way. That's by design; filtering to each
  student's best would empty the per-sitting option.
- Region and school come from the student's most recent high school enrollment,
  so a student's whole score history moves with them when they transfer, and a
  graduate shows their last high school.
- Six sub-test score types are excluded by name. Any new score type added
  upstream appears automatically.
- It deduplicates on its grain to remove kippadb's double-entered SAT sittings
  (see _Known issues, need to fix_), and a uniqueness test guards the key.

### `_current`: this year against goal

**What it shows:** this school year's progress against goal by school, region,
and network: the attempts metrics and each student's benchmark tier.

**Grain:** one row per current high school student per goal. Reads the hub,
enrollments, and the goals model (`By Grade` branch). The workbook aggregates
rows up to school, region, and network (`KTAF`, every region with current high
school students).

**Worth knowing:**

- ACT goals are excluded.
- Only a total-level benchmark is grade-specific. Attempts and section
  thresholds apply to every student regardless of grade: a grade 9 student has
  taken the SAT zero times, which is a reportable answer.
- `score` holds an attempt count on Attempts rows and the best scale score on
  Benchmark rows. Every percentage divides by all students in the group (see
  _Attempts_).
- `benchmark_tier` bands each student as College-Ready, HS Grad-Ready, or No
  Benchmark Met.
- To reproduce a dashboard total, filter the goal side,
  `expected_aligned_subject_area = 'Total'`. The score side's `subject_area`
  shares its values (`Combined`, `EBRW`, `Math`) but is null for students who
  haven't tested, so filtering on it drops them from the denominator. Leaving
  the filter off blends section rows into the totals; a numerator larger than
  the denominator is the tell. Section rows carry thresholds but no goals.
- It follows the `current_academic_year` dbt variable, so it rolls over each
  July without a code change.

### `_over_time`: attainment by graduating class

**What it shows:** each graduating class's attempts and benchmark attainment,
across years.

**Grain:** one row per student per goal, for every high school student the
network has enrolled, current and past, official and practice. Reads the hub,
enrollments, and the goals model (`All Grades` branch, with the over-time goal
columns). Its uniqueness test currently warns; see _Known issues, need to fix_.

**Worth knowing:**

- `met_min_score_int` is the row-level flag. Three `met_min_score_int_overall_*`
  flags take its max over wider partitions: per score type, per aligned subject,
  and per aligned test and subject (which spans ACT and SAT). Two `alt_met_*`
  flags do the same with the one-attempt rule read as "exactly one." Pick the
  flag matching the question. One SAT score can flip the ACT row's cross-test
  flag, so count students, not rows.
- It reads each student's best score with no `rn_highest = 1` filter, so it
  shows a few historical students whom `_benchmark_calcs` reads as `No Data`
  (see _Known issues, need to fix_).
- `strategy_case` labels a student's testing pattern, computed on the official
  and practice models; `No testing history` where there is none.

### `_benchmark_calcs`: percent meeting each benchmark

**What it shows:** the share of students meeting each readiness benchmark.

**Grain:** one row per student per test type, aligned test, subject, and
benchmark tier, for each student's most recent high school enrollment, current
and past, including students with no qualifying score so they count in the
denominator. `met_benchmark_goal` reads `Met`, `Not Met`, or `No Data`. Reads
the hub, enrollments, and the Scaffold tab.

**Worth knowing:**

- Thresholds come from the current year's Scaffold rows, with ACT and growth
  rows excluded. It doesn't read the Goals tab, despite the name.
- Scores are each student's all-time best, picked in the hub, with official and
  practice kept apart.
- It excludes IEP-exempt students and students without a graduation year.
- Its scaffold join folds `ACT/SAT` to `SAT` and joins on the aligned scope.
  That works because the fold matches the hub's value; joining on
  `expected_scope` would state the intent directly.

### `_roster`: student roster

**What it shows:** current students graduating this year or later: each expected
administration's score and growth, lifetime official attempt counts per test,
SAT highlights (superscore, best EBRW, best Math), and the student's
college-readiness course section.

**Grain:** one row per student per expected administration and score category,
guarded by a uniqueness test.

**Worth knowing:**

- It starts from the Expected Assessments tab joined on region, and left joins
  scores from `int_tableau__college_assessment_roster_scores`, so an expected
  administration with no score still appears, empty.
- Miami has no rows on the Expected Assessments tab, so it drops out at that
  join. That is intentional: Miami has no college-testing cohort yet.
- Attempt counts come from the participation roster, official only.
- The course section comes from `int_students__ccr_schedule`, the student's
  college-and-career-readiness class.

### `_de`: dual enrollment

**What it shows:** dual-enrollment course results: the college course, pass or
fail, score, semester, and institution.

**Grain:** one row per student per dual-enrollment course grade, from
PowerSchool stored grades (store codes `Y1` and `Q2`) and the dual-enrollment
extension table. It doesn't touch the assessment pipeline. Its uniqueness test
currently warns; see _Known issues, need to fix_.

### `rpt_tableau__ap_assessment_dashboard`: AP

**What it shows:** the AP Overview tab: AP course enrollment against AP exam
results, by school and subject.

**Grain:** one row per high school student per academic year per AP subject
code. The subject list is the union of the student's AP courses and the AP exams
they sat, so a course with no exam and an exam with no course both appear. It
doesn't read the hub.

**Where the scores come from:** `int_assessments__ap_assessments` takes kippadb
for academic years 2010-2017 and College Board files
(`int_collegeboard__ap_unpivot`) from 2018, the first year of files.
Irregularity codes exist only in the files, so they are null before 2018. Its
crosswalk and checks are covered by the `collegeboard-id-crosswalk` skill.

**Worth knowing:**

- A College Board ID missing from the AP crosswalk drops out silently:
  `int_assessments__ap_assessments` keeps only rows with a PowerSchool
  `student_number`. Count gaps from staging, as the crosswalk skill does.
- The population is students enrolled in high school on May 1 of the school
  year, roughly exam time.
- `Calculus BC: AB Subscore` is excluded, so a BC exam counts once.
- A student in a main AP course and its recitation section gets two rows for one
  subject. Both sections are real; the model leaves them in on purpose.
- `rn_highest` ranks a student's scores per subject, but nothing filters on it,
  so a retaken exam shows both attempts.
- `test_subject_area` reads `Took course, but not AP exam.`,
  `Took AP exam, not enrolled in course.`, `Not applicable`, or the AP course
  name when the student did both.
- `expected_scope` and `expected_test_type` are literals (`AP` and `Official`
  when the student took the course, otherwise `Not applicable`), set so the tab
  can share filters with the other views.

### Not part of CARAT

`rpt_tableau__college_assessment_dashboard`,
`rpt_tableau__college_assessment_dashboard_historic`, and
`rpt_tableau__college_assessment_qc_report` sit in the same folder but are
disabled (`enabled: false`) and feed nothing.

## Supporting models

### The official model: `int_assessments__college_assessment`

Official scores from kippadb (SAT, ACT) and College Board files (PSAT), one row
per student per score type per sitting. It computes `rn_highest`, superscores,
`strategy_case`, and `previous_total_score_change`. College Board rows reach it
only when their College Board ID is in the crosswalk sheet; AP and SAT/PSAT IDs
are separate ID spaces with separate crosswalk tabs.

### The practice model: `int_assessments__college_assessment_practice`

Converts Illuminate practice responses to scale scores. An Illuminate assessment
counts as a reportable practice test only if it has rows on the Scale Score
Conversion tab; Illuminate's own labels aren't used.

| `response_type` | Grain                          | Built from                   |
| --------------- | ------------------------------ | ---------------------------- |
| `Group`         | one per response group         | Illuminate `group` rows      |
| `Subject`       | one per student per assessment | Illuminate `overall` rows    |
| `Total`         | one per student administration | the student's `Subject` rows |

Each Illuminate assessment is one subject, so totals don't exist upstream; the
model builds them. **A total is scored only when the student sat every section**
the administration expects (`expected_total_subjects_tested` on the conversion
tab); otherwise the row appears with a null score, so an incomplete sitting
stays visible. ACT averages its sections; everything else sums them. Sections
are grouped per academic year, student, `scope_round`, and grade, so two test
forms given in one round can't pool into one total.

Two things bite when editing it. Section rows borrow their score from their
`overall` sibling through a window function that must run in the CTE where both
row types are present; filtering first makes it return null everywhere,
silently. And `grouping` is a BigQuery reserved word, so aliasing the scaffold's
`expected_grouping` to it needs backticks.

### The hub: `int_assessments__all_college_assessments`

Unions the official and practice models (practice at `Subject` and `Total`
grain) and computes, once for both:

- `attempt_lifetime` and `yearly_attempts_totals` (see _Attempts_).
- The benchmark pick. `is_benchmark_eligible` excludes ACT and the sub-test
  score types; `rn_highest_benchmark_aligned_scope` tags each student's best
  row; `benchmark_aligned_scope_max_score` carries the same value on every row,
  and keeps an `rn_highest = 1` filter that `_benchmark_calcs` inherits (see
  _Known issues, need to fix_). Both partition on `subject_area`, so PSAT 10 and
  NMSQT fold, and on `test_type`, so practice never competes with official.
- `aligned_month_round`: the month on official rows and the `scope_round` on
  practice rows, so the Expected Assessments tab joins both with one predicate.
- `previous_score_change`: the change from the student's previous sitting of the
  same score type, official or practice. Nothing reads it yet.

Some columns are official-only and read null on practice rows: `salesforce_id`,
`aligned_subject`, the score-shape counts, `surrogate_key`, and the superscore
fields.

### Goals with thresholds: `int_google_sheets__kippfwd__goals_unpivot`

Pairs each goal on the Goals tab with its threshold from the Scaffold tab. It
has two branches, and a reader filters `goal_branch`:

| `goal_branch` | Grade handling                     | Read by                                                        |
| ------------- | ---------------------------------- | -------------------------------------------------------------- |
| `By Grade`    | grade from the Goals tab           | `_current`, and the participation roster (attempts goals only) |
| `All Grades`  | no grade; uses the over-time goals | `_over_time`, the long KIPP Forward sheet                      |

- A score type with goals at two grades appears once per grade. Grouping a
  benchmark metric by `expected_metric_label` alone averages two classes into
  one wrong number; keep `grade_level` in the grouping.
- Section thresholds carry no grade, which is what applies them to every
  student.
- Attempts exist only on total rows; the model drops attempts rows for sections.
- A goal whose score type has no Scaffold row doesn't appear;
  `test_kippfwd_goals_resolve_to_scaffold` flags it.
- `expected_metric_label` (`sat_1_attempt`) is the pivot token;
  `expected_metric_name` is the display label `_over_time` shows.

### Roster scores: `int_tableau__college_assessment_roster_scores`

Each expected administration a current student has a score for, across their
high school history, feeding `_roster` and the wide KIPP Forward sheet. Each row
carries a `Scale Score`, and SAT rows also carry a `Score Change` (see
_Growth_). A reader shows the change only where the tab has a Growth row for
that administration.

It inner joins enrollments to the Expected Assessments tab on region and grade,
then to the hub on `test_type`, `score_type`, `aligned_month_round`, and, for
SAT only, academic year. SAT needs the year because grades 11 and 12 both have a
Winter season covering December and January. The PSATs stay unbound on purpose:
PSAT NMSQT is usually sat in grade 11, but the tab carries it at grade 10 only,
and leaving the year unbound is what lets those scores land on the grade 10 row.
A student who sat NMSQT in both grades shows only their best score there
(`TODO(#4658)`).

### Participation: `int_students__college_assessment_participation_roster`

Lifetime and yearly attempt counts per student and test type, from the hub's
attempt fields, with the attempts goals attached. Its grain includes
`test_type`, so a reader wanting official counts filters `test_type` as well as
`rn_lifetime = 1`.

### The KIPP Forward Google Sheets extracts

`rpt_gsheets__college_assessments_long` and
`rpt_gsheets__college_assessments_wide` feed sheets KIPP Forward reads directly.
Both keep practice separate from official.

- **Long:** `administration_type` is `Official` or `Practice`. Its `test_type`
  column holds the test (`scope as test_type`), so filtering `test_type` for
  official versus practice returns nothing.
- **Wide:** every score column without `practice` in its name is official.
  Practice has its own score columns and attempt counts. Adding an
  administration to the Expected Assessments tab means adding its practice
  column here too, or practice scores for it have nowhere to appear.

## The Google Sheets

The four KIPP Forward tabs are in one workbook; ask the data team for access.
Changes from KIPP Forward are entered by the data team, and the
`carat-dashboard` skill generates each paste as a whole tab or block in
tab-separated form, because hand edits are how mistakes get in.

| Tab                      | Staging model                                                 | Holds                                                     |
| ------------------------ | ------------------------------------------------------------- | --------------------------------------------------------- |
| `Scale Score Conversion` | `stg_google_sheets__kippfwd__practice_scale_score_conversion` | Raw-to-scale bands per practice assessment                |
| `Scaffold`               | `stg_google_sheets__kippfwd__scaffold`                        | Every valid test and score type per year, with thresholds |
| `Goals`                  | `stg_google_sheets__kippfwd__goals`                           | Goal percentages per year, test type, grade, class        |
| `Expected Assessments`   | `stg_google_sheets__kippfwd__expected_assessments`            | Seasons and months per region, grade, and test            |

The College Board ID crosswalks are in a separate workbook, covered by the
`collegeboard-id-crosswalk` skill.

### Scale Score Conversion and Scaffold

The practice model splits its reference data across these two tabs. The rule of
thumb: a value that repeats across every band of an assessment is vocabulary and
belongs on Scaffold; a value that varies band to band belongs on Scale Score
Conversion. `score_type` is on both, because it's what joins them.

Adding a practice administration touches both. Conversion bands with no matching
Scaffold row are dropped by an inner join, with no error. That join keys on
academic year, test, and score type, not grade, so **deleting a Scaffold row
excludes that score type for every grade that year**. That is how AY2023's grade
9-10 SAT is excluded.

Scale Score Conversion:

- Scale scores come from the `LOWER` column of the published tables, so a
  perfect digital SAT section reads 790, not 800.
- `aligned_scale_score` puts a score on its section's reporting scale. It
  differs only for legacy grade 9-10 SAT Reading and Writing, which are 10-40
  test scores multiplied by 10.
- `expected_total_subjects_tested` is how many sections an administration has: 4
  for ACT, 3 for the legacy grade 9-10 SAT, 2 otherwise.
- `scope_round` must differ between two administrations of one test in one year,
  or their sections sum into one total.

Scaffold:

- The key is (`academic_year`, `expected_test_type`, `expected_scope`,
  `expected_grade_level`, `expected_score_type`). Grade is in it because AY2023
  ran two SAT forms at once.
- `expected_grade_level` is a string that can hold a list (`11,12`).
- The three alignment columns fold differently and aren't interchangeable:

  | Column                          | ACT Reading vs EBRW | Growth vs Total |
  | ------------------------------- | ------------------- | --------------- |
  | `expected_subject_area`         | separate            | merged          |
  | `expected_aligned_subject_area` | merged              | merged          |
  | `expected_grouping`             | separate            | separate        |

### How the sheets are read

- **Columns map by position.** Each source declares its columns and skips the
  header row, so the Nth sheet column is the Nth declared column. Inserting a
  column mid-tab shifts every value after it, silently; renaming a header needs
  no dbt change.
- **Named ranges bound what's read.** Goals, Scaffold, and Expected Assessments
  are read through named ranges, and a paste that runs past a range's end is
  ignored. Scale Score Conversion is read by tab name.
- **A column change needs `stage_external_sources`** with
  `ext_full_refresh: true`. A value edit doesn't.

## Decisions

### AY2023 grade 9 and 10 SAT is not reported

KIPP Forward ruled those administrations invalid: grades 9 and 10 should have
taken PSAT 8/9 and PSAT 10, not a full SAT form. They are excluded by the
absence of AY2023 SAT Practice rows on the Scaffold tab. Their conversion bands
remain and are inert. AY2023 grade 11 ACT is valid and reports.

### Some practice SAT in Illuminate is not reported

Illuminate holds practice SAT from SY24-25 and SY25-26 that has no conversion
rows, so it doesn't reach CARAT. KIPP Forward hasn't asked for it; reporting it
would need the scale-score tables for those forms.

### One published scale score is corrected

College Board's PSAT 8/9 Practice Test 1 guide converts a perfect Reading and
Writing raw score (66) to 700, below raw 65's 710. For assessment 226308, raw 66
is entered as 720. A PSAT 8/9 Reading and Writing 720 is ours; the guide
says 700. PSAT 8/9 can't reach 1440 regardless: its sections top out at 710
and 690.

## Known issues, need to fix

Each of these has a test or a documented symptom, and none is fixed yet.

### `_over_time` duplicates some rows

`_over_time` groups by `strategy_case`, and a student whose `strategy_case`
differs between two rows of one score type appears twice for that goal. The
uniqueness test on (`student_number`, `expected_test_type`,
`expected_score_type`, `expected_metric_name`) warns on those rows. A percentage
the workbook computes over rows counts those students twice. The fix is to
settle `strategy_case` to one value per student and score type before the group
by, or to drop it from the grain if the workbook doesn't use it; the Over Time
tab's visible filters don't include it. Tracked in #4871.

### `_de` duplicates some stored grades

Two separate problems, and the test catches only the first.

- **Extension-table fan-out.** Some PowerSchool stored grades match more than
  one row in the dual-enrollment extension table, with different course, score,
  or semester values, so the view carries two or three rows for one grade. The
  uniqueness test on (`student_number`, `storedgrades_dcid`) warns on them.
- **`Q2` and `Y1` for the same course.** Institutions submit grades twice a
  year, and it has already happened that fall's `Q2` and spring's `Y1` both land
  for one course in one year. The student then has two stored grades, so two
  rows, and the test doesn't see it because the `storedgrades_dcid` values
  differ. The view has more rows than student-course-years, and a `TODO` in the
  model marks where a priority rule would go.

Also, about four in ten rows have no match in the extension table, so their
course, score, and institution are empty. `unique_identifier` is not a key; use
`storedgrades_dcid`. The fix is to decide which extension row wins for a stored
grade and which store code wins for a course-year.

### Pre-2016 SAT is on the old 2400 scale

SAT sittings before March 2016 are on the 2400 scale (three sections), but every
threshold is on the 1600 scale. Those scores rate high against the benchmarks,
which inflates attainment for graduating classes through about 2017 in
`_over_time` and `_scores`. They're separable by `test_date < '2016-03-01'`. The
fix is to exclude or rescale them; ACT is unaffected.

### Duplicate kippadb test records

Some scores are entered twice in kippadb, as two records with the same student,
test, and date. Tracked in #4871. Counted by record, grouped on student, test,
date, and subject:

- **SAT:** the double-entered spring 2026 school-day load was cleaned up in
  Salesforce. One October 2015 sitting remains, with 2 records whose scores
  differ on every section, so one of them is wrong. `_scores` still
  deduplicates, as a guard against a repeat, and attempt counts use distinct
  dates either way.
- **PSAT 2024:** 478 sittings were imported twice with identical scores. They
  don't reach CARAT, which takes PSAT from College Board files.
- **AP:** no duplicates. Students often sit several AP exams on one day, so AP
  records only look duplicated when grouped without subject.

Count duplicates by record, not on the unpivot. The unpivot has one row per
score type, so one duplicated sitting shows up once per score type: a SAT
sitting with 4 scores looks like 4 duplicates.

A warn-level uniqueness test on `int_kippadb__standardized_test_unpivot`
(student, test, score type, AP course, and date) already flags these. Once the
PSAT and SAT records are cleaned up, raise it to `error` so a new double entry
fails the build.

### `rn_highest = 1` hides some students' best scores

When a student's highest score for a score type has no test date, the official
model drops that row after ranks were assigned, leaving no rank-1 row. Anything
filtering `rn_highest = 1` then loses the student instead of falling back to
their next score. `benchmark_aligned_scope_max_score` keeps that filter, so a
few dozen historical SAT students read `No Data` in `_benchmark_calcs`, while
`_over_time`, which has no such filter, shows their scores. The fixes are
backfilling the dates in kippadb, or ranking after the null-date filter.

No test catches a null date yet: the date test on
`int_kippadb__standardized_test_unpivot` lets nulls through. Add a warn-level
`not_null` on `date` alongside the kippadb cleanup, so the count can be driven
to zero and held there.

## Possible improvements

Ideas that have been asked for, but not designed or built. None is a defect.

- **AP and dual enrollment metrics.** Participation, AP scores of 3 or higher,
  and DE grades of B or better, tracked against goals. AP is ready to build on;
  DE first needs the fixes under _Known issues, need to fix_. Tracked in #5546.
- **College Board standards.** Show the knowledge-and-skills results next to
  each official SAT. They exist only in the College Board files, from spring
  2022, so the work is a join from each kippadb sitting to its College Board
  record on student and test date (see _How official SAT reaches the
  dashboard_).
- **Flag students who didn't test with KTAF.** Mark official scores from a
  school year in which the student had no KTAF enrollment record, so results
  earned elsewhere can be told apart from results earned here.
- **AP course grades against AP exam scores.** A scatterplot per subject. The AP
  view has course enrollment and exam scores but no course grades, so this needs
  the stored grades joined in.
- **Percent met by CCR teacher.** `_roster` already carries the student's
  college-and-career-readiness course, section, and teacher from
  `int_students__ccr_schedule`. `_current` and `_benchmark_calcs` don't, so the
  met-benchmark tabs can't be cut by CCR teacher yet.
- **Results by student group.** The views carry IEP, 504, and English learner
  status, but not gender, race, or free and reduced-price lunch status. Adding
  them makes small groups likely, and the repo has no automatic small-cell
  suppression (#4237), so decide how to suppress before building.
- **AP Potential.** College Board's AP Potential report, which predicts AP
  success from PSAT results, isn't ingested.
- **A guide for dashboard users.** This manual is for the people who maintain
  CARAT. A short user guide or walkthrough video for the landing page was
  planned and not made.

## Yearly upkeep

| Who          | Does what                                                                                        |
| ------------ | ------------------------------------------------------------------------------------------------ |
| KIPP Forward | Decides goals, thresholds, the testing calendar, and which practice tests are given              |
| KIPP Forward | Supplies practice-test scale scores (or the College Board scoring guide) and Illuminate links    |
| Data team    | Turns those into sheet rows with the skill, pastes them, and verifies the rebuild                |
| Data team    | Matches new College Board IDs, runs the pipeline check, and sends KIPP Forward a summary         |
| Automatic    | Sheet edits rebuild staging; `current_academic_year` rolls over in July; Tableau refreshes daily |

Each school year, with KIPP Forward:

1. **Practice assessments.** For each new practice administration, add
   conversion rows and Scaffold rows. The skill derives the details from the
   Illuminate assessment and generates the rows.
2. **Seasons.** Add new administrations, including new practice rounds, to the
   Expected Assessments spec and regenerate the tab.
3. **Goals.** Enter the year's goals on the Goals tab.
4. **Rollover.** `current_academic_year` rolls over each July, network-wide, and
   `_current`, `_benchmark_calcs`, and `_roster` follow it. Before that, the new
   year's Illuminate sessions must exist, which is owned outside the data team;
   a missing Scaffold year also fails silently, as empty rows. After rollover,
   check that `_current` has rows for the new year:

   ```sql
   select academic_year, expected_test_type, count(*) as goal_rows,
   from
       `teamster-332318.kipptaf_tableau.rpt_tableau__college_assessment_dashboard_current`
   group by academic_year, expected_test_type
   ```

5. **Official scores.** When College Board files arrive, match new College Board
   IDs with the `collegeboard-id-crosswalk` skill. It then runs the CARAT
   pipeline check and drafts a summary for KIPP Forward.
