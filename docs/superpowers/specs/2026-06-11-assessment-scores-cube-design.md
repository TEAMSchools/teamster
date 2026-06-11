# Assessment-scores semantic layer — design

Anchor issue: [#4163](https://github.com/TEAMSchools/teamster/issues/4163).
Follow-ups: [#4164](https://github.com/TEAMSchools/teamster/issues/4164)
(normalized canonical dim),
[#4165](https://github.com/TEAMSchools/teamster/issues/4165) (section teacher).

## Purpose

A broad, all-source assessment-score explorer in the Cube semantic layer over
`fct_assessment_scores_enrollment_scoped`, covering internal Illuminate interims
and NJ/FL state assessments (NJSLA, NJGPA, FAST). The headline metric is
proficiency/mastery rate, which is the only score measure that is meaningful
across the incompatible score scales of the different sources. Analysts slice by
subject, score source, testing season, school/region, grade level, and student
demographics, and can drill from aggregates to row-level scores and to the
individual member assessments behind a score.

## Source fact

`fct_assessment_scores_enrollment_scoped` — grain: one row per student x
assessment x administration. PK `assessment_score_key`. The fact is thin: its
only measures are `scale_score` (null for internal), `percent_correct` (null for
state), `proficiency_level`, and `is_mastery`. Everything an analyst slices by
lives on parent dims. The fact FKs to `dim_assessment_administrations`
(`assessment_administration_key`), `dim_student_section_enrollments`
(`student_section_enrollment_key`), and `dim_dates` (`test_date_key`), and
carries `enrollment_resolution` (`subject_section` / `homeroom`).

This is event-grained (one row per test event), not a cumulative daily-status
fact, so it is **not** a snapshot cube — no `SNAPSHOT_CUBES` entry and no
`is_latest_record` / `_month_end` / `_week_end` machinery.

## Verified findings (drove the design)

All confirmed against prod (`kipptaf_marts`, `kipptaf_assessments`) during
brainstorming:

- **Location never diverges.** Across 14,189,742 fact rows, the student's
  enrollment `location_key` and the course-section `location_key` never differ
  (0 divergent rows); the student path is null on 13,878 rows (0.1%, grade-99 /
  placeholder schools) where the course path is populated. Decision: single
  canonical location join via the student enrollment; `course_sections`
  `location_key` is unused in the cube.
- **`dim_assessments` is member-grain for Illuminate.** Joining it directly to
  the fact fans out up to 30x on 19% (2,268 / 12,209) of Illuminate
  administrations. Within an administration, `academic_subject` and
  `is_internal_assessment` are constant (0 varying); `title` varies (2,135
  administrations), so the canonical title must be used, not a member title.
- **Member is multi-valued per score; canonical is single.** Of 14.16M internal
  score rows, 96.5% map to exactly one member assessment, 2.8% to two, and 0.7%
  to three or more (max 23). The rollup `array_agg`s members into
  `assessment_ids`. So canonical can be a clean single parent; member requires a
  bridge.

## Architecture

### Cube inventory

Six new cubes, reusing six existing (`student_enrollments`, `students`,
`locations`, `regions`, `dates`, `terms`):

| New cube                            | Reads                                       | Folder                      | Student-gated |
| ----------------------------------- | ------------------------------------------- | --------------------------- | ------------- |
| `student_assessment_scores` (fact)  | `fct_assessment_scores_enrollment_scoped`   | `cubes/student_assessment/` | yes           |
| `student_section_enrollments`       | `dim_student_section_enrollments`           | `cubes/students/`           | yes           |
| `assessment_administrations`        | `dim_assessment_administrations` (enriched) | `cubes/assessments/`        | no            |
| `assessments`                       | `dim_assessments` (member-grain)            | `cubes/assessments/`        | no            |
| `course_sections`                   | `dim_course_sections`                       | `cubes/conformed/`          | no            |
| `courses`                           | `dim_courses`                               | `cubes/conformed/`          | no            |
| `assessment_score_members` (bridge) | `bridge_assessment_score_members`           | `cubes/student_assessment/` | no            |

Student-domain cubes are `student`-prefixed so `cube.js`'s `isStudentMember`
gating and location scoping auto-apply; curriculum and assessment-reference dims
are unprefixed (no student data, no domain tier).

### Join graph

```text
student_assessment_scores (fct)
  - dates                      test_date_key                       (only date join; avoids diamond)
  - assessment_administrations assessment_administration_key       (canonical + occurrence/season)
  - student_section_enrollments student_section_enrollment_key
      - student_enrollments    student_enrollment_key
          - students           student_key                         (identity / demographics)
          - locations          location_key  (canonical location)
              - regions        region_key
      - course_sections        course_section_key
          - courses            course_key    (enrolled-course subject/title)
      - terms                  term_key
  - (bridge) assessment_score_members assessment_score_key
      - assessments            assessment_key (member-grain; drill-down only)
```

### Diamond / role-play resolutions

1. **`dates`** — two routes exist (fact `test_date_key`; administration
   `administered_date_key`). Only the fact joins `dates` (the score's
   `test_date`). `assessment_administrations` exposes `administered_date` as a
   degenerate `CAST(... AS TIMESTAMP)` with no `dates` join.
2. **`locations`** — only `student_enrollments` to `locations`. The
   `course_sections` `location_key` is not joined (verified never divergent).
3. **`academic_year`** — present on `student_section_enrollments`,
   `student_enrollments`, and `terms`. Exposed canonically from
   `student_section_enrollments` only, to avoid multi-cube ambiguity in views.
4. **canonical assessment** — reached through `assessment_administrations` (the
   administration determines the canonical). The fact deliberately has no direct
   canonical FK, which would diamond against the administration.

## dbt changes (additive only)

### Enrich `dim_assessment_administrations`

Project descriptors that already exist in the model's `all_administrations`
union but are dropped in the final SELECT: `title` (the **canonical** title for
Illuminate — sourced from `int_assessments__assessments_canonical`),
`academic_subject` (from `subject_area`), `type` (from `assessment_type`),
`scope`, `grade_level_tested` (from `grade_level`), and a derived
`is_internal_assessment` (= `assessment_type = 'illuminate'`). Surface the
existing `source_assessment_id` as the canonical-assessment id (Illuminate).
This is the canonical-assessment anchor and the sole source of
`administration_period` (testing season / window). No surrogate-key hash change
(none of these are hash inputs). Update the contract YAML and any `select *`
consumers.

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

### No change

`fct_assessment_scores_enrollment_scoped` itself (canonical reached via the
administration; no degenerate columns) and `dim_assessments` (already has every
member column).

## Cube measures

Defined on `student_assessment_scores`; used in the detail and summary views
only (never the member-detail view, where the bridge fan-out would
double-count):

| Measure               | Definition                                          | Notes                                                                                                                        |
| --------------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `count_scores`        | `count_distinct assessment_score_key`               | score-record count                                                                                                           |
| `count_students`      | `count_distinct student_enrollment_key` (via chain) | per student-year, matching the attendance convention                                                                         |
| `pct_proficient`      | `_count_proficient / count_scores`, percent         | headline; `is_mastery`-based, source-agnostic                                                                                |
| `avg_percent_correct` | `avg(percent_correct)`                              | internal-effective; filter by subject/module                                                                                 |
| `avg_scale_score`     | `avg(scale_score)`                                  | guardrail docs: meaningful only filtered to a single assessment + subject + grade + source; steers users to `pct_proficient` |

`_count_proficient` is a private helper (count where `is_mastery`).

## Cube dimensions

On the fact: `assessment_score_key` (PK), `test_date`, `enrollment_resolution`
(load-bearing filter — subject is only meaningful on `subject_section` rows),
`proficiency_level`, `is_mastery`, `scale_score`, `percent_correct`.

From joined cubes (subject appears twice, prefix-disambiguated):

- `assessment_administrations`: `academic_subject` (the assessment's subject),
  `title`, `type`, `scope`, `grade_level_tested`, `is_internal_assessment`
  (score source), `administration_period` (season/window), `test_type`,
  `administered_date`, `source_assessment_id` (canonical id).
- `courses`: `academic_subject` (enrolled-course subject), `course_title`,
  `course_code`.
- `course_sections`: `identifier`, `period`.
- `assessments` (member, drill-down view only): `title`, `academic_subject`,
  `module_code`, `module_type`, `grade_level_tested`, `is_internal_assessment`.
- `student_section_enrollments`: `academic_year` (canonical), `entry_date`,
  `exit_date`, `is_dropped_section`, `is_dropped_course`.
- `student_enrollments`: `grade_level`, `graduation_year`, `is_retained_year`.
- `students`: `full_name` + identifiers (PII), `race`, `gender_identity`,
  `is_gifted`, `enrollment_status`.
- `locations`: `location_name`, `abbreviation`, `grade_band`, `campus`, `city`;
  `regions`: `region_name`, `state`.
- `terms`: `semester`, `term_name`, `term_code`, `term_type`.

## Views

Three analyst-facing views:

- **`student_assessment_scores_detail`** — row-level scores; carries `full_name`
  / identifiers. Two-policy access: `cube-access-student-data` with PII fields
  in `excludes`, plus `cube-access-student-pii` with `includes: "*"`. Does
  **not** join the member bridge (keeps measures clean). Canonical and the
  assessment descriptors come from `assessment_administrations`.
- **`student_assessment_scores_summary`** — aggregates and demographic
  breakdowns only; no direct identifiers. Single `cube-access-student-data`
  policy.
- **`student_assessment_scores_members_detail`** — member-level drill-down via
  the bridge to `assessments`: one row per score x member. **No aggregate
  measures**, so the 3.5% multi-member fan-out never double-counts. Each row
  shows the member (from `assessments`), its canonical and season (from
  `assessment_administrations`), and the student context. PII-gated like the
  detail view.

## Access gating

No `cube.js` change. Student-prefixed cubes inherit `isStudentMember` member
stripping and the location scope filter (resolved through the existing
`student_enrollments` to `locations` chain, as in `student_attendance`). The
assessment-reference and curriculum dims are unprefixed and carry no student
data. Not a snapshot cube, so no `SNAPSHOT_CUBES` / `SNAPSHOT_MEASURE_STEMS`
entry.

## Exposures

Add every new mart (`fct_assessment_scores_enrollment_scoped` if not already
present, `dim_assessment_administrations`, `dim_student_section_enrollments`,
`dim_course_sections`, `dim_courses`, `dim_assessments`,
`bridge_assessment_score_members`) to `cube.yml`'s
`cube_semantic_layer.depends_on`.

## Out of scope (tracked)

- Normalized `dim_canonical_assessments` with canonical + member as first-class
  linked dims — [#4164](https://github.com/TEAMSchools/teamster/issues/4164).
- Section teacher (all teachers incl. co-teachers via bridge + `dim_staff` +
  staff-domain access decision) —
  [#4165](https://github.com/TEAMSchools/teamster/issues/4165).

## Validation approach

- Build the enriched administration dim and the bridge in a dev schema; confirm
  uniqueness/relationships tests pass and the bridge row counts reconcile with
  the rollup `assessment_ids` cardinality.
- Verify each cube FK populates in prod (sample non-null share; treat 99%+ null
  as a broken join).
- Compile each view via the Cube `/sql` endpoint and validate a representative
  query (`pct_proficient` by `academic_subject` x `region` x `academic_year`)
  against direct warehouse SQL.
- Confirm the member-detail view never inflates `count_scores` (the bridge is
  absent from measure paths).
