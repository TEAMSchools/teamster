# DDI Stack Data Model

## What it is

The DDI (data-driven instruction) stack turns internal Illuminate assessment
results into the dashboards, report-card feeds and planning sheets KTAF's NJ
regions run their assessment cycle on. Achievement directors enter assessments
in Illuminate and tag them in an AppSheet app; teachers administer and score
them; the stack fans the results out to:

- the **DDI Suite** Tableau workbook (two extracts: the assessment dashboard and
  the weekly DDI dashboard),
- the **assessment entry audit** (on the Data Quality Dashboard) and the **sight
  words dashboard** (on the Literacy Dashboard),
- four **DeansList extracts** that put scores on report cards and progress
  reports,
- two **Google Sheets** (the NJ DDI tier roster and the DeansList mod audit),
- the **AppSheet catalog feed** that closes the tagging loop, and
- the Illuminate branch of the **assessment Cube** (the star schema behind
  `student_assessment_scores_view`).

"Internal assessment" here means an Illuminate assessment someone tagged in the
AppSheet — the tag is literally what makes it internal (see Terms). The stack
covers the three NJ regions. Miami's final year on it is SY25-26; Miami returns
when Focus assessment data is ingested, and there is no interim exception.

Owner: Anthony Walters, Director, Data. Marya Shukla owns assessment-tagging
quality control in the AppSheet and the standard-domains lookup; achievement
directors enter their own assessments.

## How it fits together

```text
Illuminate DnA (dlt sync)        AppSheet tagging app          Assessments
27 stg_illuminate__* tables      (Marya Shukla + ADs)          lookup sheet
+ 46 repository_* stubs               |    ^                   (5 named ranges)
       |                              v    |                        |
       |               stg_google_appsheet__illuminate_             |
       |               assessments_extension                        |
       |                              |        rpt_appsheet__       |
       v                              v        assessments ---------+--> AppSheet
int_illuminate__assessments --> int_assessments__assessments_members    (catalog
       |                              |                                  feed)
       |                              v
int_illuminate__agg_student_    int_assessments__assessments_canonical
responses (overall/standard/          |
group)                                v
       |                int_assessments__scaffold  <-- course enrollments,
       |                 ("expected to take")          Illuminate sessions
       v                              |
int_assessments__response_rollup  <---+  <-- performance bands, reporting terms
       |         |          |         |
       v         v          v         v
DDI Suite    DeansList   mod audit   assessment star (dim_assessments,
(2 Tableau   extracts    sheet       administrations, bridges,
extracts)    (4 CDO      + tier      fct_assessment_scores_*) --> Cube view
             feeds)      roster
```

`int_illuminate__repository_data` (custom student-data tables) feeds the sight
words dashboard and the DeansList sight-words extract on a separate track from
the response rollup. On the star side, `int_assessments__score_anchors` and
`int_assessments__resolved_section_enrollments` sit between the scaffold and
`fct_assessment_scores_enrollment_scoped`, tying each score to one course
section.

### Materialization and freshness

Every `rpt_*` extract in the family is a **view**. Under them, the staging layer
is all **tables** (the 27 `stg_illuminate__*` models, the repository stubs, the
sheet staging models, and the AppSheet staging table), as are
`int_assessments__response_rollup`, `__scaffold`, `__course_enrollments`,
`__resolved_section_enrollments`, `__score_anchors`,
`int_illuminate__root_standards`, and the table marts of the assessment star.
The remaining intermediates (`int_illuminate__*` apart from `root_standards`;
`int_assessments__assessments_members`, `__assessments_canonical`,
`__performance_bands`, `__academic_goals`) and `dim_assessment_goals` are views.
A new score therefore reaches a consumer only after:

1. The Illuminate dlt sync lands it. The assessment tables
   (`agg_student_responses*`, `students_assessments`) sync at midnight and 5pm
   daily, plus Wednesday 10am/2pm and Friday 3pm. Reference tables (performance
   bands, reporting groups, repositories) sync at **midnight only** — the root
   of [#5399](https://github.com/TEAMSchools/teamster/issues/5399): same-day
   scores on a brand-new assessment can sit unscored until the next midnight.
2. The assessment star rebuilds. `int_assessments__response_rollup`, the other
   table intermediates and the table marts share one cron tick,
   `0 0,10,13,15,17 * * *` (5x/day, Eastern). The sync and the star both fire at
   midnight and 5pm, so data from the same-hour sync can miss that star tick and
   wait for the next one — check run timestamps before promising users a refresh
   time.
3. The consumer refreshes: the DDI Suite Tableau extracts at 1am and 6pm daily
   plus Friday 4pm (exposure `ddi_suite` cron, Dagster-owned); the DeansList
   SFTP extracts at 1:25am daily; Cube's `proficiency_rollup` pre-aggregation
   daily.

## Terms

- **Internal assessment** (`is_internal_assessment`; "normed" in the workbook,
  surfaced as `is_normed_scope`): an Illuminate assessment with a row in the
  AppSheet Illuminate Assessments Extension. The flag is
  `if(iae.assessment_id is not null, ...)` in
  `int_assessments__assessments_members`. Untagged assessments still flow
  through the scaffold's non-internal branch into
  `rpt_tableau__assessment_dashboard`, so the Assessment Dashboard worksheet can
  analyze every Illuminate assessment — but the Module Dashboard and DKI
  worksheets display only normed (tagged) assessments, and the canonical
  grouping, the report-card feeds and the star's internal branch use only tagged
  ones. An untagged assessment is otherwise invisible to every consumer below
  except the raw Illuminate intermediates.
- **Canonical assessment** (`canonical_assessment_id`): internal assessments are
  created once per region/variant in Illuminate, so members that share
  `(academic_year, scope, subject_area, module_code, grade_level_id)` are
  grouped, and the lowest member `assessment_id` names the group. Miami-only
  Florida copies (AppSheet `regions_assessed` exactly `Miami`) group separately,
  so New Jersey rows never inherit a Florida title or date. Non-internal
  assessments are their own canonical. Known defect: inconsistent SY25-26
  tagging destabilizes the grouping
  ([#5654](https://github.com/TEAMSchools/teamster/issues/5654)).
- **Scope**: Illuminate's assessment category (decoded from `dna_scopes`) — Unit
  Assessment ("UA"), Cumulative Review Quizzes ("CRQ"), Cold Read Quizzes, Sight
  Words Quiz, and so on. K-1 cumulative-review and cold-read quizzes are
  relabeled `Checkpoint` in `int_illuminate__assessments`. `WPP` is a
  `module_type` value excluded from the DDI dashboard; its expansion is
  unwritten — owner to confirm.
- **Module** (`module_type`, `module_sequence`, `module_code`): the AppSheet
  tagging that sequences assessments within a scope; `module_code` is the
  concatenation (for example `UA3`). These have no Illuminate-native
  counterpart.
- **`academic_year` vs `academic_year_clean`**: Illuminate dates a school year
  by its spring (`2026` for SY25-26); the warehouse dates it by its fall
  (`2025`). `academic_year_clean = academic_year - 1` converts, and
  `int_assessments__course_enrollments` converts the other way
  (`illuminate_academic_year = cc_academic_year + 1`). Every consumer join
  crosses this boundary somewhere; when counts look shifted by exactly one year,
  check which convention each side uses.
- **`response_type`**: which aggregation a response row is — `overall` (the
  whole assessment), `standard` (one standard), or `group` (one reporting
  group). Minted in `int_illuminate__agg_student_responses` from the _name_ of
  the unioned source relation, with `response_type_id = -1` as the sentinel for
  overall rows. A **null** `response_type` on the scaffold-joined surfaces
  (`int_assessments__response_rollup`, the DDI dashboard) means
  assigned-but-not-taken; `fct_assessment_scores_enrollment_scoped` makes that
  explicit as `not_taken`.
- **`is_replacement`**: an internal-assessment sitting where the assessment's
  AppSheet-tagged grade level differs from the student's current Illuminate
  session grade — a retained or accelerated student sitting an off-grade
  assessment. Set in `int_assessments__scaffold`, with three limits that follow
  from its SQL: only Text Study, Mathematics, Social Studies and Science; only
  K-8 assessments; and only sittings that actually exist in Illuminate (the
  branch inner-joins `students_assessments`), so a not-taken off-grade
  assignment never appears. An assessment with no grade tag can never be a
  replacement. These rows bypass the course-enrollment join (null `cc_dcid`),
  are excluded from score anchoring and the enrollment-scoped bridge, and are
  carried by the student-scoped bridge instead. The sight words dashboard reuses
  the column name for the analogous off-grade-quiz case; the two are computed
  independently.
- **Performance bands**: Illuminate band sets attached per response type in
  `int_assessments__performance_bands`. `int_illuminate__performance_band_sets`
  computes each band's range as `[minimum_value, next band's minimum - 0.1)`,
  top band capped at 9998.9. Each band also carries Illuminate's own
  `is_mastery` flag, so on band-driven surfaces the band set defines which
  labels count as mastery. The DeansList feeds are the exception: they hardcode
  their own ladders and cut points (see their section).
- **DDI tiers** (`nj_student_tier`), called **"buckets"** by every stakeholder
  ("Bucket 1 and 2" in tickets): the student intervention tier the tier roster
  publishes. The ladder is **not** in this family — it lives in the shared hub
  `int_extracts__student_enrollments_subjects`, and the roster passes it
  through.
- **QBLs and Power Standards**: retired programs. The lookup named range still
  exists and `rpt_tableau__ddi_dashboard` still computes `is_qbl` from it;
  finishing the retirement is
  [#5656](https://github.com/TEAMSchools/teamster/issues/5656).
  `rpt_tableau__assessment_dashboard` already hardcodes its power-standards
  columns to null for workbook compatibility.
- **Sight words**: K-2 sight-word quizzes stored as an Illuminate _repository_
  (custom student-data table), not as assessment responses — they flow through
  `int_illuminate__repository_data`, not the response rollup.
- **DKI, Module Dashboard, Mastery by Classroom**: names users bring to support
  tickets. DKI View, Module Dashboard and Mastery by Classroom are worksheets
  inside the DDI Suite workbook; DKI is also the name of the recurring data
  meeting the dashboard preps, so "the DKI dashboard" in a ticket means the DDI
  Suite. (What DKI expands to is not yet written down — owner to confirm.)

## Where the data comes from

- **Illuminate DnA and Repositories**, via the dlt sync (27 staging tables plus
  46 enabled `repository_<id>` stubs; layout and the repository-model mechanics
  are in `src/dbt/kipptaf/models/illuminate/CLAUDE.md`). Only repositories
  443-472 are on the dlt schedules; the 16 enabled stubs below 443 never sync,
  so their data is frozen (known issue). Owned by the data team; assessment
  content is owned by the achievement directors who build it.
- **The AppSheet Illuminate Assessments Extension**: the tagging app writes a
  BigQuery table read as
  `stg_google_appsheet__illuminate_assessments_extension`. The app's item list
  comes back out of the warehouse as `rpt_appsheet__assessments`, so the loop
  is: catalog feed → staff tag in the app → tags land in BigQuery → tags drive
  everything. Marya Shukla runs QC; achievement directors tag their own
  assessments.
- **The Assessments lookup spreadsheet** (ask the data team for it): one
  spreadsheet, five named ranges, five staging models — `standard_domains`
  (Marya Shukla), `academic_goals`, `course_subject_crosswalk`,
  `vendor_subject_crosswalk` (data team), and the retired
  `qbls_power_standards`. All five externals share the spreadsheet's URI, so an
  edit to any tab re-triggers all five sources together.
- **Shared hubs** (out of family, one line each):
  - `int_extracts__student_enrollments` / `_weeks` / `_subjects`: enrollment,
    demographics, week scaffold, and the subject-level supplement (tiers, iReady
    proficiency, state proficiency) the dashboards and tier roster read.
  - `base_powerschool__course_enrollments`: course/section/teacher context,
    joined on `illuminate_subject_area`.
  - `stg_google_sheets__reporting__terms`: RT-type reporting terms, date-range
    joined for term labels and term keys.
  - `stg_google_sheets__people__locations`: school-to-region mapping in the
    scaffold.
  - SchoolMint Grow + `int_performance_management__observation_details`: the
    walkthrough branch of the DDI dashboard.
  - `int_iready__instruction_by_lesson_union`: weekly iReady lesson-pass counts
    on the DDI dashboard.
- **Adjacent, not in family**: `rpt_ln__*` (the roster feed _into_ Illuminate:
  courses, enrollment, users, terms), and the non-Illuminate branches of the
  assessment star (Amplify/DIBELS, iReady, STAR, college, AP, state), which
  belong to the DIBELS, CARAT and STAT families.

## The DDI Suite workbook

Tableau exposure `ddi_suite`, two extracts, both views.
`rpt_tableau__assessment_dashboard` drives the Assessment Dashboard and Module
Dashboard worksheets; `rpt_tableau__ddi_dashboard` drives the weekly worksheets
(the DKI View; tickets also name a Mastery by Classroom worksheet whose extract
the owner should confirm). The full worksheet-to-filter breakdown still needs
the owner's walkthrough or a workbook download.

### rpt_tableau__assessment_dashboard

- **What it shows**: Illuminate assessment response rows (overall, standard and
  group level) joined to enrollment, course/teacher and student-subject context.
  Carries every Illuminate assessment, tagged or not, with `is_normed_scope`
  marking the tagged ones; drives the Assessment Dashboard worksheet (all
  assessments) and the Module Dashboard worksheet (normed only).
- **Grain**: student x response record; the course join is pinned to one section
  per subject (`rn_student_year_illuminate_subject_desc = 1`), yet prod shows
  about 0.7% of keys duplicated exactly twice (cause untraced, measured
  2026-10-02). No uniqueness test (known issue).
- **Reads**: `int_assessments__response_rollup`,
  `int_extracts__student_enrollments` (+`_subjects`),
  `base_powerschool__course_enrollments`.
- **Worth knowing**:
  - Population: `rn_year = 1`, `grade_level != 99`, current and prior academic
    year only.
  - Miami holds **zero rows in prod** in every year (measured 2026-10-02): the
    rollup still carries Miami AY2025 responses, but none survive this model's
    enrollment join after the Focus cutover.
  - `power_standard_goal`, `is_power_standard`, `standard_domain` are hardcoded
    null — retired fields kept so the workbook's field list does not break.

### rpt_tableau__ddi_dashboard

- **What it shows**: the weekly DDI cycle — students x school week x that week's
  tagged-assessment rows (expected or taken), plus iReady lesson completion
  (ES/MS) and a staff walkthrough branch, so instruction, assessment and
  coaching sit on one axis. It is **not** one row per enrolled student per week:
  the `module_type != 'WPP'` predicate sits in the WHERE clause on the
  LEFT-joined rollup, which turns the join inner — weeks with no tagged
  assessment produce no row, and untagged assessments (null `module_type`) never
  appear. Assigned-but-not-taken rows for tagged assessments do survive (tens of
  thousands per year).
  [#4808](https://github.com/TEAMSchools/teamster/issues/4808) describes the
  same shape.
- **Grain**: three unioned branches — ES/MS (grades 0-8) and HS (9-12) at
  student x week x response row; walkthrough rows at observation-row grain with
  student columns nulled and staff overloaded into them (`student_name` is the
  staff member, `subject_area` is their microgoals, `response_type` is the
  literal `walkthrough`). No uniqueness test (known issue).
- **Reads**: `int_extracts__student_enrollments_weeks`,
  `int_assessments__response_rollup`, the standard-domains and QBLs sheets,
  `int_assessments__academic_goals`, courses, the iReady lesson union, and the
  SchoolMint Grow/performance-management chain.
- **Worth knowing**:
  - Eligibility is enrollment as of the week end (`is_enrolled_week_end`,
    `enroll_status in (0, 2, 3)`), not current status — pinning to
    `enroll_status = 0` retroactively erased withdrawn students' history
    ([#4807](https://github.com/TEAMSchools/teamster/issues/4807)).
  - The `module_type != 'WPP'` filter carries a `TODO: Remove SY26` marker, and
    it is also what makes the join inner (see the grain note above).
  - A row with a null `response_type` and null `date_taken` is
    assigned-but-not-taken; `is_complete` encodes it, and the still-open PR
    [#3576](https://github.com/TEAMSchools/teamster/pull/3576) proposes an
    `is_completion_row` flag to make completion-rate denominators explicit.
  - The ES/MS and HS branches join the QBLs sheet and the goals sheet with
    different keys (ES/MS includes `grade_level` and requires `qbl is not null`;
    HS includes neither) — deliberate, but easy to misread.
  - iReady lesson columns are ES/MS only; HS and walkthrough rows carry nulls.
  - The iReady weekly metrics undercount when keyed to the assessment subject
    ([#4808](https://github.com/TEAMSchools/teamster/issues/4808)).

## The audit dashboards

### rpt_tableau__assessment_entry_audit (Data Quality Dashboard)

- **What it shows**: expected-to-take internal assessments for the current year
  against what has actually been entered in Illuminate — the "who has not
  entered scores" view.
- **Grain**: student x expected assessment, tested as
  `(student_number, assessment_id)`.
- **Reads**: `int_assessments__scaffold`, `int_extracts__student_enrollments`
  (`enroll_status = 0` only), reporting terms,
  `int_illuminate__agg_student_responses` (`response_type = 'overall'`).
- **Worth knowing**: replacement sittings are excluded (`not is_replacement`)
  but the output still carries an `is_replacement` column hardcoded to null.

### rpt_tableau__sight_words_dashboard (Literacy Dashboard)

- **What it shows**: Sight Words Quiz results per student x quiz x word, with
  untested on-grade students kept as null-value rows; shares a workbook with the
  DIBELS dashboard (see the DIBELS family doc for that side).
- **Grain**: `(repository_id, student_number, sight_word)`, tested at
  `severity: warn`.
- **Reads**: `int_illuminate__repositories`/`__repository_data`, repository
  fields and grade levels, reporting terms,
  `int_extracts__student_enrollments_subjects` (Reading rows).
- **Worth knowing**: Paterson is excluded in both branches. The off-grade branch
  (`is_replacement = true`) keeps only _scored_ rows, while the on-grade branch
  keeps every expected student — so completion rates only mean something
  on-grade, and even there the on-grade branch applies no `enroll_status`
  filter, so withdrawn students stay in the denominator.

## DeansList report-card extracts

- **What triggers it**: the Dagster `deanslist` extract job, daily at 1:25am
  Eastern (`deanslist-annual.yaml` config; "annual" names the config rotation,
  not the cadence). Each asset queries its `rpt_deanslist__*` view and delivers
  `json.gz` to DeansList's SFTP as a custom data object (CDO).
- **Inputs**: `int_assessments__response_rollup`, the AppSheet region tags
  (`regions_report_card`, `regions_progress_report`), performance band sets,
  enrollments, the standard-domains sheet, reporting terms.
- **The four feeds**:
  - `rpt_deanslist__mod_assessment`: K-4 enrichment (non-ELA/Math) subject
    averages per term, current year only; feeds only the Enrichment table on NJ
    ES report cards. Includes Unit Assessments always — **tagged or not** — and
    other scopes only when AppSheet-tagged report-card-eligible for the
    student's region. Output `subject_area` is the literal `ENRICHMENT` (a CDO
    schema placeholder).
  - `rpt_deanslist__mod_standards`: ELA/Math/Writing reporting-group averages,
    all grades, current year only, with Writing folded into Text Study and a
    five-label mastery ladder (Advanced Mastery down to Far Below Mastery) from
    the band sets; feeds the "overall" course grades on ES report cards. Gated
    by tagging (`is_internal_assessment`) only — it has no region-tag gate.
  - `rpt_deanslist__mod_standards_domains`: K-4 progress-report (overall) and
    report-card (standard-domain) performance, with **no year filter** (it
    carries every year the rollup holds). The cut-point case lists K-2 branches
    at 90/75/60 and then unconditional branches at 85/70/50/30/0, so the
    effective K-2 ladder is Exceeds 90+, Met 75-89, Approaching 50-74 (the 60
    branch only keeps 70-74 out of the generic Met), and K-2 students fall into
    Below/Far Below under 50 like everyone else. Feeds the mastery pages on NJ
    ES report cards.
  - `rpt_deanslist__sight_words`: raw sight-word mastery per student per word,
    current year forward, with no grade or region filter (Paterson included,
    unlike the dashboard); `retested` displays as its own status but counts as
    mastered (`is_mastery = 1`). The report cards use it for the K-1 sight-words
    table.
- **Outputs**: DeansList report cards and progress reports. The AppSheet region
  tags gate `mod_standards_domains` and the non-UA scopes of `mod_assessment`;
  untagged Unit Assessments still reach the enrichment feed, and `mod_standards`
  is gated by tagging alone, not region.
- **Who runs it**: nobody by hand; the schedule runs and the AppSheet tags steer
  it. When a score is missing from a report card, check the tag first, then the
  mod audit sheet.

## The Google Sheets

### rpt_gsheets__ddi_tier_roster

One row per currently-enrolled student x iReady subject with `nj_student_tier`,
prior-year NJSLA and iReady EOY proficiency — the tier-planning roster. Pure
passthrough of `int_extracts__student_enrollments_subjects` (current year,
`rn_year = 1`, `enroll_status = 0`); the tier logic lives in that hub. Lands in
the `NJ DDI Roster - Source` sheet (exposure `nj_ddi_roster_source`). The
extract applies no region filter, so Miami rows are present and
`njsla_previous_year` carries their FAST values — accepted (2026-10-03): the
reporting sheets downstream alias the column correctly, so no SQL change.

### rpt_gsheets__deanslist_mod_audit

The QA view behind the three mod feeds: the individual pre-aggregation response
rows, with a windowed `computed_avg_pct_correct` reproducing each published
feed's GROUP BY so a published average can be checked against its inputs. Scoped
to the current and prior year — wider than `mod_assessment` and `mod_standards`
(current-year) but narrower than `mod_standards_domains`, which has no year
filter. There are no flag columns; the comparison is done by eye in the sheet.
Known gap: its `mod_standards` slice does not apply the Writing-to-Text-Study
remap the published feed applies, so Writing rows need manual reconciliation.

## The AppSheet catalog feed

`rpt_appsheet__assessments` sends the entire assessment catalog
(`int_assessments__assessments_members`, no filter) to the tagging app,
including the three region-tag fields staff edit and a 0-indexed `grade_level`.
This is the outbound half of the tagging loop; the inbound half is the AppSheet
staging table. Because `assessments_members` already left-joins the extension,
staff see their own prior tags when they open the app.

## The assessment Cube (Illuminate branch)

The assessment star — `dim_assessments`, `dim_assessment_administrations`,
`dim_assessment_goals`, `bridge_assessment_expectations_enrollment_scoped` /
`_student_scoped`, `fct_assessment_scores_enrollment_scoped` / `_student_scoped`
— is multi-source. This page covers only its Illuminate branch; Amplify/DIBELS,
iReady, STAR, college and state branches belong to their own families, and the
Cube-side reference (measure semantics, view structure) ships with PR
[#5495](https://github.com/TEAMSchools/teamster/pull/5495) under
`src/cube/mcp/project_knowledge/`.

What the Illuminate branch contributes:

- `dim_assessments` is member-grained for Illuminate (one row per
  `assessment_id`, `type = 'illuminate'`); other sources are canonical-grained.
- `dim_assessment_administrations` fans the canonical catalog out per assessed
  region; `source_assessment_id` is populated only for Illuminate.
- The two expectation bridges split the scaffold on resolvability: sittings with
  a real course enrollment go enrollment-scoped; replacement sittings and the
  synthesized K-4 Newark/Camden ES-Writing rows go student-scoped.
- `fct_assessment_scores_enrollment_scoped`'s internal branch keeps
  assigned-but-not-taken rows (`response_type = 'not_taken'`) and drops any
  score `int_assessments__resolved_section_enrollments` cannot tie to a section
  (the resolver — subject section first, then a discipline match for state
  scores, then homeroom — is the scope of record).
- **Neither fact exposes a source column.** The only reliable way to isolate
  Illuminate rows is the join path
  `assessment_administration_key -> dim_assessment_administrations.assessment_key -> dim_assessments.type = 'illuminate'`.
- The public surface is `student_assessment_scores_view`, row-level-secured per
  viewer; its `proficiency_rollup` pre-aggregation refreshes daily, which is why
  the intraday star rebuilds are invisible in Cube.

## Supporting models

In-family intermediates and their outside readers ("also read by" — a change
here moves those consumers too):

- `int_assessments__response_rollup` — the family workhorse: scaffold x
  responses x bands, one row per expected student-assessment-response. Also read
  by `rpt_gsheets__assessment_roster`, `rpt_gsheets__school_metrics_extract`,
  `rpt_tableau__miami_fast`, and `int_assessments__college_assessment_practice`
  (CARAT family), so a rollup change also moves the practice-SAT chain.
- `int_assessments__assessments_members` — also read by
  `bridge_assessment_administration_members` (disabled).
- `int_assessments__scaffold` — also read by the entry audit (in family).
- `int_assessments__academic_goals` — also read by
  `rpt_tableau__academic_goals_rollup` (mid-retirement) and
  `rpt_tableau__state_assessments_dashboard` (STAT family).
- `int_illuminate__assessments`, `__agg_student_responses_standard`,
  `stg_illuminate__public__students`, and the overall-responses staging — also
  read by `int_act__test_prep_scores` (ACT family).
- `int_illuminate__repositories` / `__repository_data` — also read by the sight
  words dashboard (in family).
- `stg_google_sheets__assessments__course_subject_crosswalk` — also read by
  `dim_courses`.

## Inputs (hand-maintained)

| Input                              | Maintainer            | Feeds                                                | Update rhythm                            |
| ---------------------------------- | --------------------- | ---------------------------------------------------- | ---------------------------------------- |
| AppSheet assessment tagging        | ADs; QC: Marya Shukla | everything (`is_internal_assessment`)                | frequent; turned over every year         |
| Standard domains named range       | Marya Shukla          | report-card domains, DDI dashboard                   | largely static                           |
| Academic goals named range         | data team             | goals on the DDI dashboard, `dim_assessment_goals`   | once a year in theory, several each fall |
| Course subject crosswalk           | data team             | `int_assessments__course_enrollments`, `dim_courses` | annual audit (below)                     |
| Vendor subject crosswalk           | data team             | state/vendor branches of the star                    | rare                                     |
| QBLs / Power Standards named range | nobody (retired)      | `rpt_tableau__ddi_dashboard.is_qbl` ([#5656])        | none                                     |

The course subject crosswalk's annual audit is worth systematizing (the family
skill should carry it as a procedure): list new courses with current-year
enrollments that are missing from the sheet, then hand the list to c3/academic
ops to confirm which are tested subjects — connected to Illuminate results,
state testing results, both, or eventually Focus Apex assessments.

[#5656]: https://github.com/TEAMSchools/teamster/issues/5656

## Decisions

- **Tag-driven scope.** The AppSheet extension, not Illuminate metadata, decides
  what is a DDI assessment. This keeps the stack robust to Illuminate's messy
  catalog (duplicates, "Copy of" titles) at the cost of making the tags a single
  point of failure.
- **Canonical grouping by attributes, not region.** Network policy is one shared
  internal assessment per module, so regional copies share a canonical id via
  their shared attributes. The one exception is Miami's own Florida versions,
  which stay in a separate group.
- **Replacement sittings are visible but unscored.** Off-grade sittings show on
  rosters and the student-scoped bridge but never anchor scores — the section
  resolver cannot place them.
- **The resolver is the scope of record for the fact.** An internal score with
  no resolvable section is dropped from
  `fct_assessment_scores_enrollment_scoped` rather than carried with a null FK.
- **NJ state history is capped at 7 years in the fact; FL is not.**
- **5x/day star, daily Cube pre-agg.** Intraday rebuilds serve Tableau; Cube
  users see daily data.
- **Miami exit.** Miami's Illuminate feed ended with SY25-26. Its historical
  rows stay; nothing new lands until Focus assessment data is ingested, at which
  point the internal branch grows a Focus source (decided 2026-09-30).

## Support themes

What people actually ask about, from a keyword pass (assessment dashboard,
module dashboard, DDI, DKI) over the Zendesk warehouse copy (17 relevant
tickets) and the two Slack channels where this work is discussed (22 relevant
threads), 2026-04-02 through 2026-10-02, measured 2026-10-02. The themes, most
frequent first, and where each one points:

1. **"My assessment is not on the dashboard."** The assessment director's own
   triage rule: anything not rolling up is untagged or mistagged — wrong term
   date, wrong grade's tag, or no tag at all. When the tag is right, follow the
   freshness chain above: did the Illuminate sync land it; has the assessment
   star ticked since; has the Tableau extract refreshed. Occasionally the cause
   is genuinely on the data side (an overnight pipeline bug has reproduced this
   with tagging fully correct), so confirm the rows in the extract before and
   after a refresh rather than re-arguing the tag. After a tag fix, users expect
   a manual refresh push rather than waiting for the next tick, and they know
   the refresh times.
2. **Two worksheets disagree, or the dashboard disagrees with Illuminate.**
   Module Dashboard vs DKI View discrepancies are usually denominator questions:
   completion rows vs mastery rows (null `response_type` is
   assigned-but-not-taken), and course-enrollment vs grade-level population (an
   Algebra 1 student is in grade 8 on one cut and in the Algebra course on the
   other). A multi-assessment DKI View cut also confuses when quizzes are tagged
   to different dates per grade level — viewing by grade level is the documented
   workaround. Dashboard-vs-Illuminate discrepancies get reconciled against the
   extract rows and the sync times.
3. **Wrong or missing teacher/section.** Two distinct causes. In the model: the
   course join keeps one section per student, year and subject
   (`rn_student_year_illuminate_subject_desc = 1`), so a student's honors or
   second section is dropped from classroom rollups, and a co-teacher or
   interventionist can appear as the section of record. In the source: a wrong
   course assignment in PowerSchool rolls students up under the wrong course on
   the Module Dashboard — the fix is in PowerSchool, and it populates on the
   next morning's refresh.
4. **Access.** A blank DDI Suite page from the Launch page, or a login failure,
   is Tableau licensing or permissions — not a data defect. Route to the Tableau
   admin path before reading any SQL.
5. **Scores entered but banded wrong.** Entered answers showing a too-low
   mastery band is the shape of
   [#5399](https://github.com/TEAMSchools/teamster/issues/5399) (band tables
   sync at midnight only) — check the band-set join before suspecting the
   scores.

One recurring feature ask: averaging across module sequence numbers (for honor
roll). That is a workbook/extract change, not a data defect.

## Known issues, need to fix

Tracked elsewhere:

- [#5654](https://github.com/TEAMSchools/teamster/issues/5654) — inconsistent
  SY25-26 scope/module tagging destabilizes canonical groups.
- [#5399](https://github.com/TEAMSchools/teamster/issues/5399) — performance
  band tables sync only at midnight; same-day scores stay unscored intraday.
- [#4808](https://github.com/TEAMSchools/teamster/issues/4808) — DDI dashboard
  iReady metrics undercount.
- [#3797](https://github.com/TEAMSchools/teamster/issues/3797) — Illuminate
  catalog defects (ops-tracked).
- [#5349](https://github.com/TEAMSchools/teamster/issues/5349) — fragmented
  Illuminate standards codes.
- [#4173](https://github.com/TEAMSchools/teamster/issues/4173) /
  [#4174](https://github.com/TEAMSchools/teamster/issues/4174) — mart orphan
  rows (college-practice module codes; 5 pre-existing expectation orphans).
- [#5656](https://github.com/TEAMSchools/teamster/issues/5656) — finish retiring
  QBLs/Power Standards (the sheet staging model and `is_qbl`).
- [#4446](https://github.com/TEAMSchools/teamster/issues/4446) — Illuminate dlt
  sync refactor.
- [#5700](https://github.com/TEAMSchools/teamster/issues/5700) — the sight-words
  dashboard's warn-level uniqueness test fails in prod (about 5,500 duplicate
  keys, measured 2026-10-03): 6 SY21-22 Sight Words quizzes carry placeholder
  `TBD` word fields in Illuminate. Fixed in Illuminate, not dbt.

Found during the documentation run, not yet tracked separately:

- Uniqueness tests cover every family model with a prod-verified clean grain;
  two still lack one: `rpt_tableau__assessment_dashboard` (no clean key exists —
  the ~0.7% duplicated keys above) and `rpt_tableau__ddi_dashboard` (its
  properties YAML is in flight on PR
  [#3576](https://github.com/TEAMSchools/teamster/pull/3576)).
- The academic-goals sheet holds 2 duplicated key rows (one AY2024, one AY2025
  subject-level HS goal, each entered twice); they flow through
  `int_assessments__academic_goals` and are masked downstream by
  `dim_assessment_goals`' highest-school-goal-wins dedupe. Check: `group by` the
  5 goal keys `having count(*) > 1`.
- `rpt_tableau__assessment_dashboard`'s description carries a stale Miami row
  count and says Miami AY2026 rows have "not landed upstream yet"; prod holds
  zero Miami rows in any year and none will land — Miami left the stack.
- `dim_assessments` documentation points at
  `bridge_assessment_administration_members` as the member drill-down, but that
  bridge is disabled with zero consumers.
- `int_illuminate__performance_band_sets` carries a commented-out
  `materialized: table` override — decide and either enable or delete it.
- The 16 enabled repository stubs below 443 are absent from the dlt schedules,
  so their repository data is frozen (see Where the data comes from).
- The mod audit's Writing remap gap and its year-scope mismatch with
  `mod_standards_domains` (see its section).
- The `NJ DDI Roster - Source` sheet sits in the Reports drive folder despite
  its name, and no Reports-layer IMPORTRANGE consumer of either extract sheet
  was found — confirm how people actually read them.
- `rpt_tableau__ddi_dashboard`'s `TODO: Remove SY26` filter on
  `module_type != 'WPP'`, which is also what makes its rollup join inner.

## Yearly upkeep

1. July: the `current_academic_year` var rollover (repo-wide, not
   family-specific) moves every current-year filter in the family at once.
2. Before the first administration: achievement directors create the year's
   assessments in Illuminate and tag them in the AppSheet; Marya Shukla QCs the
   tags. Nothing shows anywhere until this happens.
3. Goals: add the new year's rows to the academic-goals named range.
4. Standard domains: update the named range when standards or domains change.
5. Reporting terms: confirm the year's RT rows exist (shared hub, but this
   family breaks visibly when they lag).
6. August: turn the DDI Suite Tableau refresh schedule back on and review its
   cron list with the assessment director — anything to add or remove for the
   year.
7. Fall: bump the DDI Suite workbook tabs' default year to the new school year
   (a workbook edit, requested every year).
8. Fall: run the course subject crosswalk audit (see Inputs) — new courses with
   current-year enrollments that the sheet is missing, confirmed with
   c3/academic ops.
9. Check the DDI Suite after the first assessment window: the first real rows
   exercise the whole chain.
