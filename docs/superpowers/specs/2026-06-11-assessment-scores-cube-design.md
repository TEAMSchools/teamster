# Assessment-scores semantic layer — design

Anchor issue: [#4163](https://github.com/TEAMSchools/teamster/issues/4163).
Follow-ups: [#4164](https://github.com/TEAMSchools/teamster/issues/4164)
(normalized canonical dim),
[#4165](https://github.com/TEAMSchools/teamster/issues/4165) (section teacher),
[#4167](https://github.com/TEAMSchools/teamster/issues/4167) (academic-goals
dim), [#4168](https://github.com/TEAMSchools/teamster/issues/4168)
(student-subject intervention-status dim).

## Purpose

A broad, all-source assessment-score explorer in the Cube semantic layer over
`fct_assessment_scores_enrollment_scoped`, covering internal Illuminate interims
and NJ/FL state assessments (NJSLA, NJGPA, FAST). The headline metric is
proficiency/mastery rate, which is the only score measure that is meaningful
across the incompatible score scales of the different sources. Analysts slice by
standard/skill, subject, score source, testing season, administration date,
school/region, grade level, course, and student demographics, and can drill from
aggregates to row-level scores and to the individual member assessments behind a
score. Dimension parity is benchmarked against the existing
`rpt_tableau__ddi_dashboard` Tableau extract.

## Source fact

`fct_assessment_scores_enrollment_scoped` — grain: one row per student x
assessment x administration x **response type**. The response type
(`response_type` / `response_type_id` / `response_type_code`) is part of the
surrogate key but is currently dropped from the output; it is the standard /
skill / overall breakdown that mastery-by-standard reporting depends on, so this
spec projects it (additive — see dbt changes). PK `assessment_score_key`.

The fact's intrinsic measures are `scale_score` (null for internal),
`percent_correct` (null for state), `proficiency_level`, and `is_mastery`.
Descriptive attributes live on parent dims. The fact FKs to
`dim_assessment_administrations` (`assessment_administration_key`),
`dim_student_section_enrollments` (`student_section_enrollment_key`), and
`dim_dates` (`test_date_key` = the student's `date_taken` / completion date),
and carries `enrollment_resolution` (`subject_section` / `homeroom`).

Event-grained (one row per scored response), not a cumulative daily-status fact,
so it is **not** a snapshot cube — no `SNAPSHOT_CUBES` entry and no
`is_latest_record` machinery.

## Verified findings (drove the design)

All confirmed against prod (`kipptaf_marts`, `kipptaf_assessments`) during
brainstorming:

- **Location never diverges.** Across 14,189,742 fact rows, the student's
  enrollment `location_key` and the course-section `location_key` never differ
  (0 divergent rows); the student path is null on 13,878 rows (0.1%, grade-99 /
  placeholder schools). Decision: single canonical location join via the student
  enrollment; `course_sections` `location_key` is unused in the cube.
- **`dim_assessments` is member-grain for Illuminate.** Joining it directly to
  the fact fans out up to 30x on 19% (2,268 / 12,209) of administrations. Within
  an administration, `academic_subject` and `is_internal_assessment` are
  constant (0 varying); `title` varies (member-level), so the canonical title is
  used. The administration does **not** FK to `dim_assessments` and cannot — its
  key uses the canonical id, `dim_assessments`' uses the member id.
- **Member is multi-valued per score; canonical is single.** Of 14.16M internal
  score rows, 96.5% map to one member, 2.8% to two, 0.7% to three or more (max
  23). Canonical can be a clean single parent (via the administration); member
  needs a bridge.

## Architecture

### Cube inventory

Eight new cubes, reusing six existing (`student_enrollments`, `students`,
`locations`, `regions`, `dates`, `terms`):

| New cube                             | Reads                                       | Folder                      | Student-gated |
| ------------------------------------ | ------------------------------------------- | --------------------------- | ------------- |
| `student_assessment_scores` (fact)   | `fct_assessment_scores_enrollment_scoped`   | `cubes/student_assessment/` | yes           |
| `student_section_enrollments`        | `dim_student_section_enrollments`           | `cubes/students/`           | yes           |
| `assessment_administrations`         | `dim_assessment_administrations` (enriched) | `cubes/assessments/`        | no            |
| `assessments`                        | `dim_assessments` (member-grain)            | `cubes/assessments/`        | no            |
| `course_sections`                    | `dim_course_sections`                       | `cubes/conformed/`          | no            |
| `courses`                            | `dim_courses` (enriched)                    | `cubes/conformed/`          | no            |
| `assessment_score_members` (bridge)  | `bridge_assessment_score_members`           | `cubes/student_assessment/` | no            |
| `administration_dates` (role-played) | `dim_dates`                                 | `cubes/conformed/`          | no            |

Student-domain cubes are `student`-prefixed so `cube.js`'s `isStudentMember`
gating and location scoping auto-apply; curriculum, assessment-reference, and
date dims are unprefixed (no student data, no domain tier). `standard_domain` is
carried as a degenerate column on the fact (1:1 lookup on `response_type_code`),
not a separate cube.

### Join graph

```text
student_assessment_scores (fct)
  - dates                      test_date_key (date_taken / completion date)
  - assessment_administrations assessment_administration_key (canonical + occurrence/season)
      - administration_dates   administered_date_key (administered_at; primary reporting date)
  - student_section_enrollments student_section_enrollment_key
      - student_enrollments    student_enrollment_key
          - students           student_key                  (identity / demographics)
          - locations          location_key  (canonical location)
              - regions        region_key
      - course_sections        course_section_key
          - courses            course_key    (course title/code/subject/is_foundations)
      - terms                  term_key
  - (bridge) assessment_score_members assessment_score_key
      - assessments            assessment_key (member-grain; drill-down only)
```

### Diamond / role-play resolutions

1. **`dates` (role-played, not collapsed).** Two genuinely different dates: the
   fact's `test_date_key` (= `date_taken`, completion) and the administration's
   `administered_date_key` (= `administered_at`, the primary reporting date,
   populated for Illuminate, null for state). These are role-playing dimensions,
   not a diamond: the fact joins the conformed `dates` cube on `test_date_key`,
   and a second cube instance `administration_dates` (same `dim_dates` table) is
   joined from `assessment_administrations` on `administered_date_key`. Two
   single-path joins to two distinct cube instances — no shared target row.
   Views prefix-disambiguate (`dates_*` vs `administration_dates_*`).
2. **`locations`** — only `student_enrollments` to `locations`. The
   `course_sections` `location_key` is not joined (verified never divergent).
3. **`academic_year`** — present on `student_section_enrollments`,
   `student_enrollments`, and `terms`. Exposed canonically from
   `student_section_enrollments` only.
4. **canonical assessment** — reached through `assessment_administrations`. The
   fact has no direct canonical FK (would diamond against the administration).

## dbt changes (additive only)

### `fct_assessment_scores_enrollment_scoped` (additive columns)

Project response-grain and band attributes already available in
`int_assessments__response_rollup` but currently dropped: `response_type`,
`response_type_code`, `response_type_description`,
`response_type_root_description`, `is_replacement`,
`performance_band_label_number`. Add `standard_domain` as a degenerate column
via the existing `stg_google_sheets__assessments__standard_domains` lookup on
`response_type_code`. **No surrogate-key hash change** — `response_type` is
already a hash input; these are pure additive projections. Update the contract
YAML and any `select *` consumers.

### Enrich `dim_assessment_administrations`

Project descriptors already in the model's `all_administrations` union but
dropped in the final SELECT: `title` (the canonical title for Illuminate),
`academic_subject` (from `subject_area`), `type` (from `assessment_type`),
`scope`, `grade_level_tested` (from `grade_level`), `module_code`, and a derived
`is_internal_assessment` (= `assessment_type = 'illuminate'`). Also add
`module_type` (source onto the canonical grain) and surface
`source_assessment_id` as the canonical-assessment id. No hash change. This is
the canonical-assessment anchor and the sole source of `administration_period`
(season/window).

### Enrich other dims (additive)

- `dim_courses`: add `is_foundations` (derived today in
  `int_assessments__course_enrollments`). `course_number` is already exposed as
  `course_code`.
- `dim_student_enrollment_status`: add `status_504`, `is_self_contained`,
  `is_sipps`. (`ml_status` is already covered by `is_ell`; `iep_status` by
  `is_iep` / `iep_classification`.)
- `dim_student_enrollments`: add `year_in_network`. (`cohort` is already covered
  by `graduation_year`.)
- `dim_locations`: add `head_of_school`.

### New `bridge_assessment_score_members`

Factless bridge: `assessment_score_key` to member `assessment_key`. Internal:
reconstruct `assessment_score_key` from the same inputs the fact uses and unnest
the rollup `assessment_ids` to member ids, hashing each to the member
`assessment_key`
(`surrogate('illuminate', module_code, member_assessment_id, null)`). State: map
the single state `assessment_key`
(`surrogate(assessment_type, module_code, null, null)`). Properties + tests
(`unique_combination_of_columns` on the two keys; `relationships` to the fact
and to `dim_assessments`).

## Cube measures

Defined on `student_assessment_scores`; used in the detail and summary views
only (never the member-detail view, where the bridge fan-out would
double-count). With `response_type` projected, these aggregate at the
standard/skill grain when filtered by `response_type` / `response_type_code`:

| Measure               | Definition                                          | Notes                                                                                 |
| --------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `count_scores`        | `count_distinct assessment_score_key`               | scored-response count                                                                 |
| `count_students`      | `count_distinct student_enrollment_key` (via chain) | per student-year, matching the attendance convention                                  |
| `pct_proficient`      | `_count_proficient / count_scores`, percent         | headline; `is_mastery`-based, source-agnostic                                         |
| `avg_percent_correct` | `avg(percent_correct)`                              | internal-effective; filter by subject/standard                                        |
| `avg_scale_score`     | `avg(scale_score)`                                  | guardrail docs — meaningful only filtered to a single assessment/subject/grade/source |

`_count_proficient` is a private helper (count where `is_mastery`).

## Cube dimensions

On the fact: `assessment_score_key` (PK), `test_date`, `enrollment_resolution`
(load-bearing — subject is only meaningful on `subject_section` rows),
`proficiency_level`, `performance_band_label_number`, `is_mastery`,
`scale_score`, `percent_correct`, `response_type`, `response_type_code`,
`response_type_description`, `response_type_root_description`,
`standard_domain`, `is_replacement`.

From joined cubes (subject appears twice, prefix-disambiguated):

- `assessment_administrations`: `academic_subject`, `title`, `type`, `scope`,
  `grade_level_tested`, `is_internal_assessment`, `module_code`, `module_type`,
  `administration_period`, `test_type`, `source_assessment_id`.
- `administration_dates`: `date_day`, `month_name`, `quarter_number`,
  `academic_year`, etc. (primary reporting date).
- `dates`: completion-date calendar attributes.
- `courses`: `academic_subject`, `course_title`, `course_code`, `credit_type`,
  `is_foundations`.
- `course_sections`: `identifier`, `period`.
- `assessments` (member, drill-down view only): `title`, `academic_subject`,
  `module_code`, `module_type`, `grade_level_tested`, `is_internal_assessment`.
- `student_section_enrollments`: `academic_year` (canonical), `entry_date`,
  `exit_date`, `is_dropped_section`, `is_dropped_course`.
- `student_enrollments`: `grade_level`, `graduation_year`, `year_in_network`,
  `is_retained_year`.
- `student_enrollment_status`: `is_ell`, `is_iep`, `iep_classification`,
  `special_education_code`/`_name`/`_placement`, `status_504`,
  `is_self_contained`, `is_sipps`, `is_meal_eligible`, `meal_eligibility`.
- `students`: `full_name` + identifiers (PII), `race`, `gender_identity`,
  `is_gifted`, `enrollment_status`.
- `locations`: `location_name`, `abbreviation`, `grade_band`, `campus`, `city`,
  `head_of_school`; `regions`: `region_name`, `state`.
- `terms`: `semester`, `term_name`, `term_code`, `term_type`.

## Views

Three analyst-facing views:

- **`student_assessment_scores_detail`** — row-level scores; carries `full_name`
  / identifiers. Two-policy access: `cube-access-student-data` with PII fields
  in `excludes`, plus `cube-access-student-pii` with `includes: "*"`. Does not
  join the member bridge.
- **`student_assessment_scores_summary`** — aggregates and demographic
  breakdowns only; no direct identifiers. Single `cube-access-student-data`
  policy.
- **`student_assessment_scores_members_detail`** — member-level drill-down via
  the bridge to `assessments`: one row per score x member. No aggregate
  measures, so the multi-member fan-out never double-counts. PII-gated like the
  detail view.

## Access gating

No `cube.js` change. Student-prefixed cubes inherit `isStudentMember` member
stripping and the location scope filter (resolved through the existing
`student_enrollments` to `locations` chain). Assessment-reference, curriculum,
and date dims are unprefixed. Not a snapshot cube.

## Exposures

Add every new/enriched mart to `cube.yml`'s `cube_semantic_layer.depends_on`:
`fct_assessment_scores_enrollment_scoped`, `dim_assessment_administrations`,
`dim_student_section_enrollments`, `dim_course_sections`, `dim_courses`,
`dim_assessments`, `dim_student_enrollment_status`, `dim_student_enrollments`,
`dim_locations`, `dim_dates`, `bridge_assessment_score_members`.

## DDI dimension parity

Benchmarked against `rpt_tableau__ddi_dashboard`. Covered after this spec: all
student demographics, enrollment, school/region, status (incl. 504 /
self-contained / SIPPS), term, assessment descriptors (title, subject,
module*code/type, administered_at), the response/standard family
(`response_type*`, `standard_domain`, `is_replacement`, band number), course fields (`course\*\*`, `is_foundations`), and enrollment extras (`year_in_network`, `head_of_school`).
Intentionally **not** in this cube (separate facts/domains): iReady lessons,
walkthrough/observation data, microgoals — these belong to their own cubes.
Teacher fields are deferred (#4165).

## Out of scope (tracked)

- Normalized `dim_canonical_assessments` (canonical + member as first-class
  linked dims) — [#4164](https://github.com/TEAMSchools/teamster/issues/4164).
- Section teacher (all teachers incl. co-teachers via bridge + `dim_staff` +
  staff-domain access decision) —
  [#4165](https://github.com/TEAMSchools/teamster/issues/4165).
- Academic-goals dim (`grade`/`school`/`region`/`organization` goals via
  `dim_assessment_goals`) —
  [#4167](https://github.com/TEAMSchools/teamster/issues/4167).
- Student-subject intervention-status dim (DIBELS, state-test proficiency, NJ
  tier, FL low-25, iReady-exempt) —
  [#4168](https://github.com/TEAMSchools/teamster/issues/4168).
- QBL / power-standard flags (Google Sheet) — not currently tracked; raise if
  needed.

## Validation approach

- Build the enriched dims and the bridge in a dev schema; confirm
  uniqueness/relationships tests pass and the bridge row counts reconcile with
  the rollup `assessment_ids` cardinality.
- Confirm each enrichment is functionally determined by its host grain (no new
  duplicate keys) — especially `module_type` on the administration and the
  response/standard columns on the fact.
- Verify each cube FK populates in prod (treat 99%+ null as a broken join);
  expect `administration_dates` to be null for state rows by design.
- Compile each view via the Cube `/sql` endpoint and validate a representative
  query (`pct_proficient` by `response_type_code` x `region` x `academic_year`,
  and by `administration_dates` season) against direct warehouse SQL.
- Confirm the member-detail view never inflates `count_scores`.
