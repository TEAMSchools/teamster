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
proficiency/mastery rate, which is the only score measure meaningful across the
incompatible score scales of the different sources. Analysts slice by
standard/skill, subject, score source, testing season, administration date,
school/region, grade level, course, and student demographics, and can drill from
aggregates to row-level scores and to the individual member assessments behind a
score. Dimension parity is benchmarked against the existing
`rpt_tableau__ddi_dashboard` Tableau extract.

## Source fact

`fct_assessment_scores_enrollment_scoped` — grain: one row per student x
assessment x administration x **response type**. The response type
(`response_type` / `response_type_id` / `response_type_code`) is part of the
surrogate key but currently dropped from the output; it is the standard / skill
/ overall breakdown that mastery-by-standard reporting depends on, so this spec
projects it (additive). PK `assessment_score_key`.

Intrinsic measures: `scale_score` (null for internal), `percent_correct` (null
for state), `proficiency_level`, `is_mastery`. Descriptive attributes live on
parent dims. The fact FKs to `dim_assessment_administrations`
(`assessment_administration_key`), `dim_student_section_enrollments`
(`student_section_enrollment_key`), and `dim_dates` (`test_date_key` =
`date_taken` / completion date), and carries `enrollment_resolution`
(`subject_section` / `homeroom`).

Event-grained (one row per scored response), not a cumulative daily-status fact,
so it is **not** a snapshot cube.

## Verified findings (drove the design)

All confirmed against prod (`kipptaf_marts`, `kipptaf_assessments`):

- **Location never diverges.** Across 14,189,742 fact rows, student-enrollment
  `location_key` and course-section `location_key` never differ (0 rows);
  student path null on 13,878 rows (0.1%). Single canonical location join via
  the student enrollment.
- **`dim_assessment_administrations` CAN FK to `dim_assessments` on the
  canonical id.** The canonical model sets
  `canonical_assessment_id = first_value(assessment_id)` — the canonical id is
  itself the representative member's id, and `dim_assessments` has a row per
  member. Across all 4,748 Illuminate canonicals,
  `surrogate(assessment_type, module_code, canonical_id, null)` matches a
  `dim_assessments` row 100% of the time, with **0** `title` and **0**
  `academic_subject` mismatches vs. the canonical. This join is
  many-administrations-to-one-assessment — **no fan-out**. (The 30x fan-out risk
  applies only to joining the _fact_ to all members, which is the bridge path.)
- **Member is multi-valued per score; canonical is single.** Of 14.16M internal
  score rows, 96.5% map to one member, 2.8% to two, 0.7% to three or more (max
  23). The actual member(s) a score rolled up are reached via the bridge.

## Architecture

### Cube inventory

Nine new cubes, reusing six existing (`student_enrollments`, `students`,
`locations`, `regions`, `dates`, `terms`). Two pairs are role-played (same
table, two cube instances): `dim_dates` (`dates` + `administration_dates`) and
`dim_assessments` (`assessments` + `assessment_members`).

| New cube                            | Reads                                                   | Role                                          |
| ----------------------------------- | ------------------------------------------------------- | --------------------------------------------- |
| `student_assessment_scores` (fact)  | `fct_assessment_scores_enrollment_scoped`               | scores                                        |
| `student_section_enrollments`       | `dim_student_section_enrollments`                       | enrollment bridge to student/course           |
| `assessment_administrations`        | `dim_assessment_administrations` (+`assessment_key` FK) | occurrence: season, admin date                |
| `assessments`                       | `dim_assessments`                                       | canonical descriptors (via administration FK) |
| `assessment_members`                | `dim_assessments`                                       | actual member(s) (via score bridge)           |
| `course_sections`                   | `dim_course_sections`                                   | section context                               |
| `courses`                           | `dim_courses` (+`is_foundations`)                       | course subject/title/code                     |
| `assessment_score_members` (bridge) | `bridge_assessment_score_members`                       | score to member(s)                            |
| `administration_dates`              | `dim_dates`                                             | administration-date calendar                  |

Student-domain cubes are `student`-prefixed for `cube.js` gating; assessment,
curriculum, and date dims are unprefixed. `standard_domain` is a degenerate
column on the fact (1:1 on `response_type_code`), not a cube.

### Cube join graph

```text
student_assessment_scores (fct)
  - dates                       test_date_key (completion date)
  - assessment_administrations  assessment_administration_key
      - administration_dates    administered_date_key (administered_at; primary reporting date)
      - assessments             assessment_key  (canonical descriptors; many-to-one, no fan-out)
  - student_section_enrollments student_section_enrollment_key
      - student_enrollments     student_enrollment_key
          - students            student_key
          - locations           location_key
              - regions         region_key
      - course_sections         course_section_key
          - courses             course_key
      - terms                   term_key
  - (bridge) assessment_score_members assessment_score_key
      - assessment_members      assessment_key  (actual member(s); drill-down only)
```

### dbt model references (FK graph)

Arrows point from child to the parent it references (`*` marks a model touched
by this spec; `[NEW]` is created by it).

```text
fct_assessment_scores_enrollment_scoped *
  |-- assessment_administration_key --> dim_assessment_administrations *
  |                                        |-- assessment_key [NEW FK] --> dim_assessments
  |                                        '-- administered_date_key ----> dim_dates
  |-- student_section_enrollment_key --> dim_student_section_enrollments
  |                                        |-- student_enrollment_key --> dim_student_enrollments *
  |                                        |                                |-- student_key --> dim_students
  |                                        |                                '-- location_key --> dim_locations *
  |                                        |                                                      '-- region_key --> dim_regions
  |                                        |-- course_section_key --> dim_course_sections
  |                                        |                            '-- course_key --> dim_courses *
  |                                        '-- term_key --> dim_terms
  '-- test_date_key --> dim_dates

bridge_assessment_score_members [NEW]
  |-- assessment_score_key --> fct_assessment_scores_enrollment_scoped *
  '-- assessment_key --------> dim_assessments

dim_student_enrollment_status *   (joined to dim_student_enrollments via student_enrollment_key)
```

`dim_assessments` itself is unchanged (it already carries `title`,
`academic_subject`, `type`, `scope`, `grade_level_tested`, `module_type`,
`module_code`, `is_internal_assessment`).

### Diamond / role-play resolutions

1. **`dim_dates` (role-played).** Fact `test_date_key` (completion) joins
   `dates`; administration `administered_date_key` (administered_at, primary
   reporting date; null for state) joins a second instance
   `administration_dates`. Two instances, two single-path joins — no diamond.
2. **`dim_assessments` (role-played).** Canonical descriptors reached via
   `assessment_administrations → assessments` (FK on `assessment_key`, the
   canonical-representative row, single, no fan-out). Actual member(s) reached
   via `bridge → assessment_members`. Two instances avoid a diamond.
3. **`locations`** — single join via `student_enrollments`; `course_sections`
   `location_key` unused.
4. **`academic_year`** — exposed canonically from `student_section_enrollments`.
5. **canonical assessment** — reached through the administration FK, not a
   direct fact FK (which would diamond against the administration).

## dbt changes (additive only)

### `fct_assessment_scores_enrollment_scoped`

Project response-grain attributes already in `int_assessments__response_rollup`
but dropped: `response_type`, `response_type_code`, `response_type_description`,
`response_type_root_description`, `is_replacement`,
`performance_band_label_number`. Add `standard_domain` (degenerate, via
`stg_google_sheets__assessments__standard_domains` on `response_type_code`). No
hash change (`response_type` is already a hash input). Update the contract YAML
and any `select *` consumers.

### `dim_assessment_administrations`

Add **one** column: `assessment_key` =
`generate_surrogate_key([assessment_type, module_code, source_assessment_id, test_type])`
(all four already in the `all_administrations` CTE). For Illuminate this
resolves to the canonical-representative `dim_assessments` row; for state it's
the 1:1 state row. Add a `relationships` test to `dim_assessments`. No
descriptor denormalization, no hash change. (Existing columns —
`administered_date_key`, `_dbt_source_project`, `administration_period`,
`source_assessment_id`, `test_type` — stay.)

### Other dims (additive)

- `dim_courses`: add `is_foundations` (derived today in
  `int_assessments__course_enrollments`). `course_number` already exposed as
  `course_code`.
- `dim_student_enrollment_status`: add `status_504`, `is_self_contained`,
  `is_sipps`. (`ml_status` covered by `is_ell`; `iep_status` by `is_iep` /
  `iep_classification`.)
- `dim_student_enrollments`: add `year_in_network`. (`cohort` covered by
  `graduation_year`.)
- `dim_locations`: add `head_of_school`.

No change to `int_assessments__assessments_canonical` — `module_type` comes from
`dim_assessments` via the administration FK.

### New `bridge_assessment_score_members`

Factless bridge: `assessment_score_key` to member `assessment_key`. Internal:
reconstruct `assessment_score_key` from the fact's inputs and unnest the rollup
`assessment_ids` to member ids, hashing each to
`surrogate('illuminate', module_code, member_assessment_id, null)`. State: the
single state `assessment_key`. Tests: `unique_combination_of_columns` on the two
keys; `relationships` to the fact and to `dim_assessments`.

## Cube measures

On `student_assessment_scores`; detail + summary views only (never the member
view — bridge fan-out):

| Measure               | Definition                                  | Notes                                                        |
| --------------------- | ------------------------------------------- | ------------------------------------------------------------ |
| `count_scores`        | `count_distinct assessment_score_key`       | scored-response count                                        |
| `count_students`      | `count_distinct student_enrollment_key`     | per student-year                                             |
| `pct_proficient`      | `_count_proficient / count_scores`, percent | headline, source-agnostic                                    |
| `avg_percent_correct` | `avg(percent_correct)`                      | internal-effective; filter by subject/standard               |
| `avg_scale_score`     | `avg(scale_score)`                          | guardrail docs — single assessment/subject/grade/source only |

## Cube dimensions

On the fact: `assessment_score_key` (PK), `test_date`, `enrollment_resolution`,
`proficiency_level`, `performance_band_label_number`, `is_mastery`,
`scale_score`, `percent_correct`, `response_type`, `response_type_code`,
`response_type_description`, `response_type_root_description`,
`standard_domain`, `is_replacement`.

From joined cubes:

- `assessments` (canonical descriptors, via administration): `title`,
  `academic_subject`, `type`, `scope`, `grade_level_tested`, `module_type`,
  `module_code`, `is_internal_assessment`.
- `assessment_administrations`: `administration_period`, `test_type`,
  `source_assessment_id` (canonical id).
- `administration_dates`: administration-date calendar attributes (primary
  reporting date). `dates`: completion-date attributes.
- `assessment_members` (member view only): `title`, `academic_subject`,
  `module_code`, `module_type`, `grade_level_tested`.
- `courses`: `academic_subject`, `course_title`, `course_code`, `credit_type`,
  `is_foundations`. `course_sections`: `identifier`, `period`.
- `student_section_enrollments`: `academic_year`, `entry_date`, `exit_date`,
  `is_dropped_section`, `is_dropped_course`.
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

- **`student_assessment_scores_detail`** — row-level; `full_name` / identifiers;
  two-policy access (PII fields in `excludes` + a `cube-access-student-pii`
  `includes: "*"`). Reads `assessments` (canonical) via the administration; does
  not join the member bridge.
- **`student_assessment_scores_summary`** — aggregates + demographic breakdowns;
  single `cube-access-student-data` policy.
- **`student_assessment_scores_members_detail`** — member drill-down via bridge
  to `assessment_members`; one row per score x member; no aggregate measures.

## Access gating

No `cube.js` change. Student-prefixed cubes inherit `isStudentMember` gating and
location scoping. Assessment/curriculum/date dims unprefixed. Not a snapshot
cube.

## Exposures

Add every new/touched mart to `cube.yml`'s `cube_semantic_layer.depends_on`:
`fct_assessment_scores_enrollment_scoped`, `dim_assessment_administrations`,
`dim_assessments`, `dim_student_section_enrollments`, `dim_course_sections`,
`dim_courses`, `dim_student_enrollment_status`, `dim_student_enrollments`,
`dim_locations`, `dim_dates`, `bridge_assessment_score_members`.

## DDI dimension parity

Benchmarked against `rpt_tableau__ddi_dashboard`. Covered after this spec: all
student demographics, enrollment, school/region, status (incl. 504 /
self-contained / SIPPS), term, assessment descriptors (title, subject,
module_code/type via the `dim_assessments` FK, administered_at), the
response/standard family, course fields (incl. `is_foundations`), and enrollment
extras (`year_in_network`, `head_of_school`). Intentionally **not** in this cube
(separate facts/domains): iReady lessons, walkthrough/observation data,
microgoals. Teacher fields deferred (#4165).

## Out of scope (tracked)

- Normalized `dim_canonical_assessments` —
  [#4164](https://github.com/TEAMSchools/teamster/issues/4164).
- Section teacher —
  [#4165](https://github.com/TEAMSchools/teamster/issues/4165).
- Academic-goals dim —
  [#4167](https://github.com/TEAMSchools/teamster/issues/4167).
- Student-subject intervention-status dim —
  [#4168](https://github.com/TEAMSchools/teamster/issues/4168).
- QBL / power-standard flags — not currently tracked.

## Validation approach

- Build the enriched dims + bridge in a dev schema; confirm uniqueness /
  relationships tests pass; reconcile bridge row counts with the rollup
  `assessment_ids` cardinality.
- **Confirm the `assessment_key` FK on `dim_assessment_administrations`
  populates for the state branches** (Illuminate proven 100%; state is
  structurally 1:1 but unverified empirically).
- Verify each cube FK populates in prod; expect `administration_dates` null for
  state rows by design.
- Compile each view via Cube `/sql`; validate `pct_proficient` by
  `response_type_code` x `region` x `academic_year` and by administration season
  against direct warehouse SQL.
- Confirm the member view never inflates `count_scores`.
