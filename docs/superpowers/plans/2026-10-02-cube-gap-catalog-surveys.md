# Cube Gap Catalog — Surveys

Part of the [Cube Connector Gap Catalog](2026-10-02-cube-gap-catalog.md). Refs
#5673. One section per core-set dashboard; tables and notes are the per-workbook
inventory extracted from the production .twb and classified against the dbt
marts and Cube model YAML as of 2026-10-02.

## Survey Dashboard (`survey_dashboard`)

- workbook: Survey Dashboard | contentUrl `SurveyDashboard_17078426466440` |
  luid `b11542a2-6780-4feb-a1dd-534ffe724faf` | project Production
- upstream datasources: `rpt_tableau__survey_responses` (embedded),
  `rpt_tableau__survey_completion (kipptaf_tableau)` (embedded) — both
  single-table embedded extracts, no shared published datasource
- rpt_/source models in use: `rpt_tableau__survey_responses`,
  `rpt_tableau__survey_completion`, `rpt_tableau__survey_links` (feeds
  completion), upstream `int_surveys__survey_responses`,
  `int_people__staff_roster_history`, `int_people__staff_roster`,
  `int_people__location_crosswalk`, `int_students__teacher_grade_levels`
- published dashboards inventoried: Home, Intent to Return, ITR Detail, ITR
  Analysis, Support, Support Trends, Support Feedback (7)
- sheets excluded as hidden/scratch: 2 — `Data Lab: AI Summary` dashboard (not
  in the server's published view list; its zones are text/parameter-control
  only, zero worksheet zones — a static LLM-summarizer scratch page linking an
  external Google Sheet feedback form, no warehouse-backed metric); `Sheet 19`
  worksheet (not placed on any dashboard zone, not hidden in `<windows>` either
  — an orphaned department/job-title breakdown sheet, excluded from Measures
  below)
- regions served by this dashboard overall: all (Newark, Camden, Miami,
  Paterson) — confirmed from the RLS formulas (`Permissions - Support`,
  `Permissions - Completion`, `Permissions - ITR`): KTAF-administered staff
  surveys are network-wide; row-level security narrows what an individual
  _viewer_ sees (by AD group and their own region/school/department), it does
  not exclude any region from the underlying data. NJ regional staff, KIPP Miami
  staff, and Paterson TEAM Staff are each named explicitly in the RLS formulas.

### Measures

| metric                                                                    | agg                                                                                                        | source field / formula (trimmed)                                                           | dashboards                                                               | status               | where                                                                                                                                                                                                                                                                                                                   | regions                                          |
| ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------ | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| Completion %                                                              | CountD/CountD                                                                                              | `COUNTD(survey_response_id)/COUNTD(employee_number)`                                       | Home (Completion Tracking)                                               | mart-ready           | `bridge_survey_expectations` (expected respondents) LEFT JOIN `fct_survey_submissions` on staff_key+survey_administration_key                                                                                                                                                                                           | all                                              |
| Completion (binary did/didn't respond)                                    | shape/attr encoding                                                                                        | `completion` column, 0/1                                                                   | Home (Individual Tracking)                                               | mart-ready           | same as above, per-respondent grain                                                                                                                                                                                                                                                                                     | all                                              |
| Respondent count                                                          | CountD employee_number                                                                                     | `COUNTD(employee_number)`                                                                  | ITR BAN, ITR Drilldown, Support BAN, support_heat, support_yoy(tooltip)  | mart-ready           | `fct_survey_submissions.staff_key` (CountD)                                                                                                                                                                                                                                                                             | all                                              |
| Submission count                                                          | CountD survey_response_id                                                                                  | `COUNTD(survey_response_id)`                                                               | Completion Tracking                                                      | mart-ready           | `fct_survey_submissions.survey_submission_key`                                                                                                                                                                                                                                                                          | all                                              |
| Answer Value Calc                                                         | none (row-level decode)                                                                                    | `IFNULL(answer_value, IIF(answer='Strongly Agree',5,...))` 5-pt Likert decode              | Support BAN, support_heat, support_yoy, support_yoy_question (as filter) | mart-ready           | `fct_survey_responses.response_value` (model description: "cast from raw answer text")                                                                                                                                                                                                                                  | all                                              |
| % Agree + Strongly Agree                                                  | Avg                                                                                                        | `IIF([Answer Value Calc] >= 4, 1, 0)`, averaged                                            | Support BAN, support_heat, support_yoy, support_yoy_question             | mart-ready, with gap | `fct_survey_responses.response_value` computes the base rate; needs `dim_survey_questions` to carry a question-group/department-rating attribute to reproduce the workbook's "Cut By" slicing (see Dimensions gap below)                                                                                                | all                                              |
| Count Agree/Strongly Agree >= 90%                                         | Sum (of an LOD-computed 0/1 flag)                                                                          | `INT({INCLUDE [Question Shortname (group)] : AVG(%Agree) >= 0.90})`                        | Support BAN                                                              | mart-ready, with gap | same base as above; the 90% threshold flag itself is a Tableau-side LOD calc, reproducible as a having-clause aggregate over the same mart measure                                                                                                                                                                      | all                                              |
| ITR reason-for-leaving text                                               | row-level text (grouped by answer)                                                                         | raw `answer` text, grouped under "Reasons for Leaving" question set                        | ITR_reasons_leaving                                                      | mart-ready           | `fct_survey_responses.response_text` joined to `dim_survey_questions`                                                                                                                                                                                                                                                   | all                                              |
| ITR reason-for-staying text                                               | row-level text                                                                                             | same pattern, different question set                                                       | ITR_reasons_staying                                                      | mart-ready           | same as above                                                                                                                                                                                                                                                                                                           | all                                              |
| ITR individual response detail                                            | row-level text, by respondent x question                                                                   | raw `answer` per respondent/question                                                       | ITR Individual Response                                                  | mart-ready           | `fct_survey_responses` + `dim_survey_questions` + `dim_staff` (respondent identity — PII, see Notes)                                                                                                                                                                                                                    | all                                              |
| Support open-ended answers                                                | row-level text, by question/term                                                                           | raw `answer` filtered to open-ended question flag                                          | Support Feedback (support_open_ended)                                    | mart-missing         | the open-ended-question classifier (`Open Ended Filter` calc: question_shortname contains `_oe`/`_text`/`open`) is workbook-side; `dim_survey_questions.type` (SCALE/TEXT/RADIO/etc.) could substitute but isn't yet populated for this filter's exact logic — logic otherwise lives in `int_surveys__survey_responses` | all                                              |
| Survey Term (Spring/Fall split)                                           | dimension-as-measure (text label on Trends)                                                                | `IF MONTH(date_submitted)>=1 AND <7 THEN academic_year+' Spring' ELSEIF >=7 THEN +' Fall'` | Support Trends, Support Feedback (title), KTAF Support Trends Title      | mart-ready           | `dim_survey_administrations` (academic_year) joined to `dim_terms` (term_key) already carries term type/name; Spring/Fall split would reuse `dim_terms` rather than re-deriving from date                                                                                                                               | all                                              |
| Year-over-year avg trend                                                  | Avg, by Survey Term x Question                                                                             | `Calculation_87960977061396481 (survey term) x AVG(Answer Value Calc)`                     | support_yoy, support_yoy_question                                        | mart-ready           | `fct_survey_responses.response_value` aggregated by `dim_survey_administrations`/`dim_terms` and `dim_survey_questions`                                                                                                                                                                                                 | all                                              |
| "Cut By" dimension switch                                                 | parameter-driven CASE (location / location-group / business unit / job group / department / race / gender) | `IF [Cut By param]='Location' THEN location_clean_name ELSEIF ... END`                     | Support BAN, support_heat, support_yoy                                   | workbook-only        | the parameter-swap mechanism itself is Tableau-native; each underlying branch dimension is separately mart-ready (see Dimensions)                                                                                                                                                                                       | all                                              |
| RLS: Permissions - Support / Permissions - Completion / Permissions - ITR | boolean gate (filter shelf)                                                                                | AD-group (`ISMEMBEROF`) + manager/self/region/school/department membership tests           | all sheets (filter shelf on every worksheet)                             | workbook-only        | no Cube or mart equivalent exists; row-level security design is a separate exercise from this gap catalog                                                                                                                                                                                                               | all (gates the _viewer_, not the row population) |
| RLS: Department Gate / Respondent Is Regional Leadership                  | boolean gate                                                                                               | job_title/department pattern matching + AD group checks                                    | Support sheets, ITR Permissions chain                                    | workbook-only        | same as above                                                                                                                                                                                                                                                                                                           | all                                              |
| Question + Job Group Filter                                               | boolean gate (eligibility: which job titles see which questions)                                           | large CASE over `question_shortname` x `job_title`/`home_department_name`                  | Support BAN, support_heat, support_yoy, support_open_ended               | workbook-only        | encodes Support-survey question eligibility by role; no mart/cube equivalent                                                                                                                                                                                                                                            | all                                              |

### Dimensions

| dimension                                                                           | used as                                                                              | status                                                          | where                                                                                                                                                                                                                                                                                    | regions |
| ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Location (`location_clean_name`)                                                    | rows/filter, most sheets                                                             | mart-ready                                                      | `dim_locations` / `dim_staff` work-assignment join (location is not a direct `dim_staff` column — see gap below)                                                                                                                                                                         | all     |
| Job Title                                                                           | filter/rows, most sheets                                                             | mart-ready, with gap                                            | not present on `dim_staff` itself (checked: no `job_title` column) — lives on a staff work-assignment mart/fact that FKs to `dim_staff`; confirm the exact model before building                                                                                                         | all     |
| Home Business Unit / Home Department                                                | filter, most sheets                                                                  | mart-ready, with gap                                            | same gap as Job Title — region/department resolve via a work-assignment join, not `dim_staff` directly                                                                                                                                                                                   | all     |
| Survey / Survey Title / Survey Round                                                | cols/filter                                                                          | mart-ready                                                      | `dim_surveys.name`/`.type`, `dim_survey_administrations` (term + academic_year = "round")                                                                                                                                                                                                | all     |
| Academic Year (incl. "2020+" filter variant)                                        | filter, most sheets                                                                  | mart-ready                                                      | `dim_survey_administrations.academic_year`                                                                                                                                                                                                                                               | all     |
| Question Shortname / Question Title (group)                                         | rows, Support + ITR sheets                                                           | mart-ready                                                      | `dim_survey_questions.shortname` / `.text`                                                                                                                                                                                                                                               | all     |
| Answer (raw response text, incl. wildcard-search variant)                           | rows/filter                                                                          | mart-ready                                                      | `fct_survey_responses.response_text`                                                                                                                                                                                                                                                     | all     |
| Respondent Name / Teammate (preferred_name_lastfirst)                               | rows (ITR Individual Response, Completion individual tracking)                       | mart-ready (PII)                                                | `dim_staff.full_name` — direct identifier, exclude from any outbound extract per PII rules                                                                                                                                                                                               | all     |
| Race/Ethnicity, Gender                                                              | "Cut By" branch options                                                              | mart-ready                                                      | `dim_staff.race`, `dim_staff.gender_identity`                                                                                                                                                                                                                                            | all     |
| Manager name / manager email (reports_to_*)                                         | RLS input only, not displayed                                                        | mart-ready (PII)                                                | `dim_staff` reports-to fields (not confirmed on current dim_staff properties read — verify before building)                                                                                                                                                                              | all     |
| Rated Department (code/name)                                                        | implicit grouping for Support "Cut By"=Department and RLS Department Gate            | mart-missing                                                    | `int_surveys__survey_responses` / `rpt_tableau__survey_responses.sql` (`rated_department_code`, `rated_department_name`) — not present on `dim_survey_questions`                                                                                                                         | all     |
| Is Current (survey_links flag)                                                      | filter, Completion/Individual Tracking                                               | mart-missing                                                    | `rpt_tableau__survey_links` — denotes the currently-active survey-link roster row; no equivalent concept on `bridge_survey_expectations` (which already scopes to the eligible population per administration, so may be redundant rather than missing — verify before treating as a gap) | all     |
| Primary grade level taught                                                          | joined onto survey_responses (teacher context)                                       | mart-missing                                                    | `int_students__teacher_grade_levels` via `rpt_tableau__survey_responses.sql`                                                                                                                                                                                                             | all     |
| Alumni status / community grew up / community professional exp / level of education | staff bio fields used in response export, not seen on-shelf in any inventoried sheet | workbook-only (present in source extract, no shelf usage found) | `rpt_tableau__survey_responses.sql`                                                                                                                                                                                                                                                      | all     |
| Survey round (`round_rn`)                                                           | filter, ITR + Support sheets                                                         | mart-ready                                                      | `fct_survey_submissions` grain could support a rank-by-date derivation; not an existing mart column — compute at consumption                                                                                                                                                             | all     |

### Notes

- **No Cube survey model exists at all** (`src/cube/model` has zero files
  matching `survey`): every measure and dimension here is cube-missing by
  definition; the mart-ready/mart-missing split is what matters for scoping a
  future cube.
- **Two generations of survey marts coexist.** The dashboard's two embedded
  datasources read the _older_ `rpt_tableau__survey_responses` /
  `rpt_tableau__survey_completion`, which sit directly on
  `int_surveys__survey_responses` + `int_people__staff_roster_history` +
  `rpt_tableau__survey_links`. A separate, newer dimensional layer
  (`fct_survey_responses`, `fct_survey_submissions`, `dim_surveys`,
  `dim_survey_questions`, `dim_survey_administrations`,
  `bridge_survey_expectations`, `bridge_survey_questions`) already exists in
  `marts/` but — per its own properties YAML comments — is read by **no Cube
  cube and no Tableau exposure today**. Most measures here classify "mart-ready"
  against that newer layer, but it was built independently of this workbook and
  has NOT been validated end-to-end against it; expect gaps (department-rating
  code, question-eligibility-by-role, RLS inputs) beyond the ones flagged above.
- **RLS is pervasive and non-trivial.** Four separate boolean gate calcs
  (`Permissions - ITR`, `Permissions - Support`, `Permissions - Completion`,
  `RLS - Department Gate`) sit on the filter shelf of nearly every worksheet,
  keyed to Active Directory group membership plus manager/self/region/
  school/department relationships. None of this has a Cube or mart equivalent;
  porting these dashboards to Cube requires a parallel row-level-security design
  exercise, not just measure/dimension coverage.
- **`dim_staff` does not carry job title, department, or location** as inspected
  (only identity/bio/demographic columns were found in its properties YAML).
  Those fields likely live on a separate staff work-assignment dim/fact that FKs
  to `dim_staff` — this needs direct confirmation before scoping a cube, since
  nearly every measure on this dashboard is sliced by one of them. Flagged
  rather than fully resolved given scope/time.
  - Not exhaustively checked: `bridge_survey_expectations` eligibility rules in
    its description (primary/active staff, enrolled students grades 3-12, family
    contacts) were taken from its own YAML description, not independently
    verified against `int_surveys__*` logic.

### Verification

- cube-covered spot-check: N/A — zero Cube YAML files under `src/cube/model`
  reference "survey" (`grep -rl -i survey src/cube/model` returned nothing);
  there is no cube-covered row in this inventory to check.
- mart-ready spot-check: `fct_survey_responses` column `response_value`
  (`src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml`,
  described as "Numeric value of the response... Cast from the raw answer text")
  is the direct mart equivalent of the workbook's `Answer Value Calc`
  (`IFNULL([answer_value], IIF([answer]='Strongly Agree',5,...))`).
- mart-missing spot-check: `rated_department_code` / `rated_department_name`
  (the Support survey's department-rating classification, used for the "Cut By"
  = Department option and the RLS Department Gate) are selected in
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__survey_responses.sql`
  from `int_surveys__survey_responses`, and have no column on
  `dim_survey_questions` or any other mart.

## Survey HQ (Personalized Survey Links) (`survey_hq`)

- workbook: Personalized Survey Links | contentUrl `PersonalizedSurveyLinks` |
  luid `95584fbd-e5d7-425b-a1fc-9953bc2a7df9` | project Production
- upstream datasources: 1 embedded datasource, captioned
  `rpt_tableau__survey_completion (kipptaf_tableau)` — but its physical BigQuery
  relation is actually
  `[teamster-332318.kipptaf_tableau].[rpt_tableau__survey_links]` (confirmed via
  the `<connection>`/`<relation>` XML; the datasource caption is
  stale/misleading). `rpt_tableau__survey_completion` itself exists in the repo
  but is NOT what this workbook reads.
- rpt_/source models in use (from datasource + SQL trace):
  `rpt_tableau__survey_links` (direct source) → `rpt_tableau__survey_responses`
  (completion flag) → `int_people__staff_roster` (staff/roster attributes) →
  `stg_google_sheets__reporting__terms` (academic_year / round / is_current)
- published dashboards inventoried: Survey HQ (1 dashboard, 1 view on server)
- sheets excluded as hidden/scratch: 1 (`Sheet 3` — not placed on any dashboard
  zone; only `Survey Links` worksheet is in the dashboard's `<zones>`)
- regions served by this dashboard overall: all (network-wide staff, incl.
  central office/"KIPP TEAM and Family Schools Inc."). No region/district filter
  exists anywhere in the workbook or in `rpt_tableau__survey_links`'s WHERE
  clauses — some survey rows are scoped by job_title/department/business_unit
  (manager tier, school-based, "not HQ"), never by city. Row-level security is
  per-individual (`Permissions - Self`: username/samaccountname/mail match), not
  per-region.

### Measures

| metric                                                                                                                            | agg                                                               | source field / formula (trimmed)                                                                                                                | dashboards                                     | status        | where                                                                                                                                     | regions |
| --------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Completion (row-level flag, 0/1/null, NOT aggregated on the dashboard — feeds the `Completed`/`Completed Symbol` text calcs only) | none (raw int column, no Sum/Avg/CountD anywhere in the workbook) | `[completion]`; case in rpt_tableau__survey_links: null for Gallup/TNTP, else 1 if a matching `rpt_tableau__survey_responses` row exists else 0 | Survey HQ (via Survey Links sheet, indirectly) | mart-ready    | `rpt_tableau__survey_links.completion` (and upstream `fct_survey_responses`/`rpt_tableau__survey_responses` for the raw submission event) | all     |
| Shape Alignment / Text Alignment (`Calculation_353814105257136133`, `Shape Alignment (copy)`)                                     | Avg                                                               | literal constants `0` and `.5`, averaged only to anchor a shape mark's x-position                                                               | Survey HQ (Survey Links, cols shelf)           | workbook-only | n/a — pure layout/axis-padding helper                                                                                                     | n/a     |

**Note on scope**: this workbook has essentially no business-metric aggregation.
It is a per-staff-member personalized-link list (one row per person × assigned
survey), not a completion-rate or response-count dashboard. The only "measure"
role fields present (`completion`, and the two alignment calcs) are either never
aggregated for display or are pure Tableau layout plumbing. Completion is
rendered as a **dimension** (`Completed` / `Completed Symbol`, a 3-way
categorical: Complete / Not Complete Yet / Not Tracked), which is why it's also
listed under Dimensions below.

### Dimensions

| dimension                                                                                                           | used as                                                                                                                | status                                                                                                                                             | where                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | regions |
| ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Survey (`survey`)                                                                                                   | row shelf, filter                                                                                                      | mart-ready                                                                                                                                         | `rpt_tableau__survey_links.survey` (literal per UNION branch: 'Staff Info & Certification Update', 'Intent to Return Survey', 'KTAF Support Survey', 'Manager Survey', 'Support Survey', 'School Community Diagnostic', 'TNTP Insight Survey', 'Gallup Q12 Survey') — several names string-match `dim_surveys.name`'s classification struct, but there is no FK/join; `dim_surveys` is sourced from Google Forms/Alchemer/PowerSchool survey platforms, a different lineage than this hardcoded list | all     |
| Survey Assignment (calc, now a passthrough of `[assignment]` — dead commented-out branching logic)                  | row shelf                                                                                                              | mart-ready                                                                                                                                         | `rpt_tableau__survey_links.assignment`                                                                                                                                                                                                                                                                                                                                                                                                                                                               | all     |
| Completed / Completed Symbol (calc from `completion` + `survey`)                                                    | row shelf (Completed), shape encoding (Completed Symbol)                                                               | mart-ready                                                                                                                                         | derived from `rpt_tableau__survey_links.completion` + `.survey`                                                                                                                                                                                                                                                                                                                                                                                                                                      | all     |
| Link Clean (calc; resolves `[link]` with hardcoded Google Form fallback URLs per survey)                            | row shelf, tooltip                                                                                                     | mart-ready                                                                                                                                         | `rpt_tableau__survey_links.link` (the per-survey URL is itself templated in the rpt_ model's CTEs)                                                                                                                                                                                                                                                                                                                                                                                                   | all     |
| Survey Taker Name (calc; reformats `preferred_name_lastfirst` "Last, First" → "First Last")                         | cols shelf, LOD                                                                                                        | mart-ready                                                                                                                                         | `rpt_tableau__survey_links.preferred_name_lastfirst` (sourced from `int_people__staff_roster.formatted_name`; `dim_staff.full_name`/`first_name`/`last_name` are cube-exposed equivalents)                                                                                                                                                                                                                                                                                                           | all     |
| Survey Text / Survey Text (mobile) (calc; static instructional copy per survey, e.g. "look for an email from...")   | text encoding (Survey Text only — "mobile" variant is defined but referenced nowhere else in the twb; orphaned/unused) | workbook-only                                                                                                                                      | n/a — static display copy                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | n/a     |
| Academic Year (`academic_year`)                                                                                     | filter                                                                                                                 | mart-ready                                                                                                                                         | `rpt_tableau__survey_links.academic_year` (from `stg_google_sheets__reporting__terms`); `dim_dates`/term conformed dims cover academic year generally but there's no FK here                                                                                                                                                                                                                                                                                                                         | all     |
| Is Current (`is_current`)                                                                                           | filter                                                                                                                 | mart-ready                                                                                                                                         | `rpt_tableau__survey_links.is_current` (from `stg_google_sheets__reporting__terms`)                                                                                                                                                                                                                                                                                                                                                                                                                  | all     |
| Permissions - Self (calc; `LOWER(USERNAME())` matched against `username`/`samaccountname`/`mail`)                   | filter (row-level security, not a displayed field)                                                                     | mart-ready (identity fields covered by `dim_staff`: `active_directory_username`, `work_email`, `google_email` — cube-exposed via the `staff` cube) | `rpt_tableau__survey_links.username`/`.samaccountname`/`.mail`, sourced from `int_people__staff_roster`; cube: `src/cube/model/cubes/staff/staff.yml` (identity dims)                                                                                                                                                                                                                                                                                                                                | all     |
| Username / Mail / Samaccountname / Employee Number / Link (raw, on `Sheet 3` only — NOT on the published dashboard) | row shelf on excluded sheet                                                                                            | mart-ready                                                                                                                                         | same `rpt_tableau__survey_links` columns; flagged only because `Sheet 3` is hidden/unpublished, not because the fields differ                                                                                                                                                                                                                                                                                                                                                                        | all     |

### Notes

- This is the thinnest workbook inventoried in this gap-catalog pass so far: one
  dashboard, one real content worksheet, no aggregation. It functions as a
  personalized-link directory, gated by row-level security to "you see only your
  own row." There is effectively nothing here that a Cube measure/dimension view
  would meaningfully replace beyond exposing the underlying identity and
  survey-assignment fields that already exist in `dim_staff` (cube-covered) —
  the survey/assignment/link/completion fields have no Cube counterpart and no
  natural one (they're operational routing data, not analytic facts).
- The embedded datasource's caption (`rpt_tableau__survey_completion`) is
  misleading — confirmed via the `.twb`'s `<connection>`/`<relation>` elements
  that the actual table read is `rpt_tableau__survey_links`. Don't trust
  datasource captions at face value for this workbook family; verify against
  `<relation table=...>`.
- `Sheet 3` is excluded as hidden/scratch: it is not referenced in the
  dashboard's `<zones>`, so it never renders on the published "Survey HQ" view
  (the server's `get-workbook` view list shows only one view, confirming only
  the dashboard is published, not the worksheet).
- "Survey Text (mobile)" calculated field exists in the datasource but is
  referenced nowhere (count of its internal name in the `.twb` = 1, i.e. only
  its own `<column>` definition) — flagged as orphaned/dead, not included as an
  active metric.
- "Survey Assignment" calc's formula body is 100% commented out
  (`//IF [Survey] = 'One Off Staff Survey' ...`) with only `[assignment]` live —
  i.e. it's a no-op passthrough today; noted rather than treated as a meaningful
  transformation.
- Per the Asana blockers list, `fct_survey_responses`, `dim_staff`, and
  `dim_surveys` all exist in marts today, but this workbook's actual lineage
  (`rpt_tableau__survey_links` → `rpt_tableau__survey_responses` →
  `int_people__staff_roster`) does NOT read any of them — consistent with the
  sibling Survey Dashboard agent's finding that the newer dimensional survey
  marts are unread by anything in this family. A Cube migration for this
  workbook would need new Cube support for raw survey-assignment/link routing
  data (not currently modeled anywhere as a dimensional concept), or an
  acceptance that this workbook stays a direct-extract Tableau page outside
  Cube's scope since it has no analytic aggregation to replace.
- No region filter of any kind was found — treated the "network-wide staff" hint
  as confirmed, not just assumed.

### Verification

- cube-covered spot-check: N/A — no measure or dimension in this workbook has an
  actual Cube view match; the closest adjacent coverage is staff identity fields
  (`active_directory_username`, `work_email`, `google_email`) exposed in
  `src/cube/model/cubes/staff/staff.yml`, used here only for Tableau's own
  row-level-security filter, not as displayed content.
- mart-ready spot-check: `survey` / `assignment` / `link` / `completion` all
  resolve directly to columns in
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__survey_links.sql` (the
  workbook's actual source table, confirmed via the `.twb`'s
  `<relation table='[teamster-332318.kipptaf_tableau].[rpt_tableau__survey_links]'>`
  element) — e.g. `completion` is computed at lines 502-508 of that file.
- mart-missing spot-check: none found — every displayed field traces to
  `rpt_tableau__survey_links` or a static Tableau calc; nothing requires a model
  that doesn't already exist.

## Manager Survey Report (`manager_survey_report`)

- workbook: Manager Survey Reports | contentUrl `ManagerSurveyReports` | luid
  `61c1e07d-778e-40a8-81ad-327f3951c8e2` | project Production
- upstream datasources: `rpt_tableau__manager_survey_details (kipptaf_surveys)`
  (embedded, single datasource for the whole workbook)
- rpt_/source models in use (from datasource + SQL trace):
  `rpt_tableau__manager_survey_details`
  (`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__manager_survey_details.sql`),
  built from `int_surveys__manager_survey_details`, `int_people__staff_roster`,
  `int_people__location_crosswalk`
- published dashboards inventoried: `Manager Report` (1 view, `ManagerReport`)
- sheets excluded as hidden/scratch: 0 — both worksheets
  (`Manager_Individual_averages`, `Manager_individual_comments`) are on the one
  published dashboard; no `hidden='true'` windows found
- regions served by this dashboard overall: all (network-wide staff). The
  workbook's RLS calcs (`RLS - Entity Gate`, `RLS - Location Gate`) gate row
  _visibility_ per viewer's AD group across all four regions (TEAM/Newark,
  KCNA/Camden, Miami, Paterson) — the underlying extract itself carries all four
  regions with no region filter in `rpt_tableau__manager_survey_details.sql`

### Measures

| metric                                      | agg                       | source field / formula (trimmed)                                                                                                   | dashboards     | status     | where                                                                                                                                                                                                                                                                                                                           | regions |
| ------------------------------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | -------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Average answer value (manager survey score) | Avg                       | `[answer_value]` → `avg:answer_value:qk`, text mark on Manager_Individual_averages, sliced by academic year x reporting-term-group | Manager Report | mart-ready | `fct_survey_responses.response_value` (`src/dbt/kipptaf/models/marts/facts/fct_survey_responses.sql`, `manager_responses` arm reads `int_surveys__manager_survey_details.answer_value`) joined to `fct_survey_submissions` manager_submissions arm + `dim_surveys` (survey_type = 'Manager Survey'); no Cube measure exposes it | all     |
| Record count                                | Sum, tooltip-only         | `[Number of Records]` = literal `1`, summed; tooltip encoding only                                                                 | Manager Report | mart-ready | row count over `fct_survey_responses` filtered to the manager-survey arm                                                                                                                                                                                                                                                        | all     |
| Comment text (verbatim open-ended answer)   | Attribute/none, text mark | `[answer]` displayed as text on Manager_individual_comments, by term x question                                                    | Manager Report | mart-ready | `fct_survey_responses.response_text` (same model, `manager_responses.answer`)                                                                                                                                                                                                                                                   | all     |

### Dimensions

| dimension                                                                                                                                                                                                                                                                      | used as                                                                | status                                        | where                                                                                                                                                                                                                                                                                         | regions |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- | --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Campaign Academic Year (`campaign_academic_year`)                                                                                                                                                                                                                              | column shelf, filter                                                   | mart-ready                                    | `fct_survey_submissions.academic_year` (manager_submissions arm, `src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql`)                                                                                                                                                             | all     |
| Campaign Reporting Term — variants: `campaign_reporting_term` (raw), `Campaign Reporting Term (copy)` (pass-through calc), `Campaign Reporting Term (group)` (Tableau categorical-bin collapsing MGR1/MGR1r9→"Round 1", MGR2/MGR2r9→"Round 2", MGR3→"Round 3", MGR4→"Round 4") | column shelf, row shelf                                                | mart-ready                                    | `fct_survey_submissions.rt_code` / `rt_name` (joined via `stg_google_sheets__reporting__terms`, `type='SURVEY'`, `name='Manager Survey'`); the group-cleanup logic itself is workbook-only                                                                                                    | all     |
| Question Title / Question Shortname — variants: `question_title`, `question_shortname`, `Question Title (group)` (Tableau categorical-bin collapsing whitespace/punctuation dupes of the same 3 question strings)                                                              | column shelf                                                           | mart-ready                                    | `dim_survey_questions.text` / `.shortname` (`src/dbt/kipptaf/models/marts/dimensions/dim_survey_questions.sql`, alchemer_questions arm)                                                                                                                                                       | all     |
| Subject Preferred Name (`subject_preferred_name`)                                                                                                                                                                                                                              | filter, implicit grain                                                 | cube-covered (name differs, same meaning)     | `staff.full_name` (`src/cube/model/cubes/staff/staff.yml`) via `fct_survey_submissions.subject_staff_key`                                                                                                                                                                                     | all     |
| Respondent Email (`respondent_email`)                                                                                                                                                                                                                                          | filter                                                                 | cube-covered                                  | `staff.work_email` (`src/cube/model/cubes/staff/staff.yml`) via `fct_survey_submissions.staff_key` (respondent)                                                                                                                                                                               | all     |
| Home Business Unit Name (`home_business_unit_name`)                                                                                                                                                                                                                            | RLS gate input, dimension                                              | cube-covered                                  | `staff_work_history.business_unit_name` (`src/cube/model/cubes/staff/staff_work_history.yml`)                                                                                                                                                                                                 | all     |
| Location Clean Name (`location_clean_name`)                                                                                                                                                                                                                                    | RLS gate input, dimension                                              | cube-covered                                  | `locations` cube via `staff_work_history.work_location_key` (`src/cube/model/cubes/staff/staff_work_history.yml`)                                                                                                                                                                             | all     |
| Job Title (`job_title`)                                                                                                                                                                                                                                                        | RLS gate input, dimension                                              | cube-covered (name differs: `position_title`) | `staff_work_history.position_title`                                                                                                                                                                                                                                                           | all     |
| Job Function (`job_function`)                                                                                                                                                                                                                                                  | RLS gate input (Teacher/TIR check, Chief-level check)                  | mart-missing                                  | `int_people__staff_roster.job_function` (`src/dbt/kipptaf/models/people/intermediate/int_people__staff_roster.sql`) — no mart/cube column carries this exact HR job-function text; `staff_cube_access.job_function_level/code` is a different, access-tier classification, not the same field | all     |
| Mail / User Principal Name / Sam Account Name (`mail`, `user_principal_name`, `sam_account_name`)                                                                                                                                                                              | RLS "Permissions" calc input (self/manager match against `USERNAME()`) | cube-covered (approximate)                    | `staff.work_email` / `staff.active_directory_username` (`src/cube/model/cubes/staff/staff.yml`)                                                                                                                                                                                               | all     |
| Reports To Mail / Reports To Sam Account Name (`reports_to_mail`, `reports_to_sam_account_name`)                                                                                                                                                                               | RLS "Permissions" calc input                                           | mart-ready                                    | reachable via `staff_work_history.manager_staff_key` → `staff_manager` cube join, but no exposed "manager email" dimension today                                                                                                                                                              | all     |

### Notes

- **Asana coverage gap**: no Asana task exists for this dashboard in the Data
  Marts + Semantic Layer project. Flagging prominently per task instructions —
  this is a fully undocumented/untracked dashboard in the Asana backlog despite
  having a non-trivial RLS implementation and active prod usage (12,665 view
  count on the one published view, `get-workbook` response).
- **RLS plumbing excluded from the tables above**: `RLS - Entity Gate`,
  `RLS - Location Gate`, `RLS - Role Gate`, `RLS - Subject Is Senior Leader`,
  and `Permissions` (`User_test (copy)`) are Tableau row-level-security
  calculated fields, not displayed metrics/dimensions — they gate which rows a
  viewer can see (self/manager, regional ops, MDSO/HOS/MDO/AcOps, school-based
  SL/DSO/AP-of-teacher, and a special-cased "Paterson TEAM Staff" group tied to
  the two Paterson Prep locations). Classified `workbook-only` and omitted from
  the main tables to avoid inflating counts with access-control logic rather
  than reportable content. Worth noting for context: this RLS logic is
  materially more complex than a simple region filter and is NOT visible in any
  dbt/Cube source — it lives entirely in the `.twb` as `ISMEMBEROF()` calcs
  against AD security groups.
- **Important correction to this dashboard's domain hint**: the task prompt's
  "nothing reads the newer dimensional survey marts" note (from sibling-agent
  findings on the _Survey Dashboard_) does **not** hold for Manager Survey data
  specifically. `fct_survey_responses.sql` and `fct_survey_submissions.sql` both
  have dedicated `manager_responses` / `manager_submissions` arms that already
  ingest `int_surveys__manager_survey_details` and
  `int_surveys__manager_submission_subjects`, joined against
  `stg_google_sheets__reporting__terms` for term/academic-year and carrying
  `staff_key` (respondent) + `subject_staff_key` (subject under review). So the
  core score metric (avg answer_value) and the open-ended comment text are both
  already reachable through the new marts — the gap is purely that no Cube
  `surveys` cube/view exposes `fct_survey_responses` / `fct_survey_submissions`
  / `dim_surveys` / `dim_survey_questions` yet (confirmed:
  `grep -ri survey src/cube/model` turns up zero cube/view files, only
  incidental substring matches in staff/terms cubes).
- **Datasource is a single embedded extract**, not a published Tableau
  datasource — no separate datasource-level governance surface to check beyond
  the `rpt_` model itself.
- Workbook is tiny: 2 worksheets, 1 dashboard, 1 view. No device-layout
  variants, no hidden sheets.
- Judgment call: grouped the 3 near-duplicate reporting-term fields and the 3
  near-duplicate question-title fields into single dimension rows per the "group
  near-identical variants" instruction, since they are Tableau-side
  string-cleanup of the same two underlying mart columns.

### Verification

- cube-covered spot-check: `staff.work_email` is defined at
  `src/cube/model/cubes/staff/staff.yml` (line ~84, `name: work_email`,
  `sql: work_email`) — matches the workbook's Respondent Email / Mail fields in
  meaning (AD work email), joined from `fct_survey_submissions.staff_key`.
- mart-ready spot-check: `fct_survey_responses.response_value` column, defined
  in `src/dbt/kipptaf/models/marts/facts/fct_survey_responses.sql` lines 36 and
  56 (`ms.answer_value as response_value` in the `manager_responses` CTE,
  carried through `all_responses` into the final select) — this is the exact raw
  material for the workbook's `avg:answer_value:qk` measure, with no Cube
  measure defined over it today.
- mart-missing spot-check: `job_function` has no mart/cube equivalent; it is
  sourced only from
  `src/dbt/kipptaf/models/people/intermediate/int_people__staff_roster.sql`
  (`sr.job_function`, selected straight through by
  `rpt_tableau__manager_survey_details.sql` line 47) — an intermediate model,
  not a mart or cube dimension.
