# High School Early Warning Data Model

The **High School Early Warning Dashboard** is a Tableau dashboard owned by the
Data Team. It answers whether a high school student is on track to graduate,
combining three independent feeds — course performance, community service, and
New Jersey graduation pathway status.

Exposure: `high_school_early_warning_dashboard` in
`src/dbt/kipptaf/models/exposures/tableau.yml`. Tableau LSID
`6333e047-e7a9-4d8f-a740-3df30f179d11`, refreshed by Dagster at `0 6 * * *`.

!!! note "This doc is partial"

    The graduation pathway section below is complete. The community service and
    course-performance feeds are named here for lineage but not yet documented.
    Add them rather than starting a separate page.

## The three feeds

| Feed                                      | Answers                                   | Upstreams                                                                                                                                                                 |
| ----------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rpt_tableau__graduation_requirements`    | Has the student met a graduation pathway? | `int_students__graduation_path_codes`, `int_extracts__student_enrollments_subjects`, `base_powerschool__course_enrollments`                                               |
| `rpt_tableau__community_service`          | Are service hours on track?               | `int_deanslist__students__custom_fields__pivot`, `stg_deanslist__behavior`, `int_extracts__student_enrollments`                                                           |
| `rpt_tableau__hs_early_warning_dashboard` | Grades, GPA, and discipline flags         | `base_powerschool__final_grades`, `base_powerschool__sections`, `int_powerschool__gpa_term`, `int_deanslist__incidents__penalties`, `stg_google_sheets__reporting__terms` |

Miami is out of scope throughout. NJ graduation pathways do not apply in
Florida, and `int_students__graduation_path_codes` filters
`where e.region != 'Miami'`.

## Graduation pathways

`int_students__graduation_path_codes` computes `final_grad_path_code` — the
letter New Jersey uses to report which pathway a student met. It is not only a
dashboard input: it also flows through `rpt_powerschool__autocomm_students` into
the PowerSchool fields `s_nj_stu_x__graduation_pathway_ela` and
`s_nj_stu_x__graduation_pathway_math`, dropped daily for AutoComm import. **A
wrong code here becomes a wrong state submission.**

For the working rules, cut score maintenance, and the failure modes, use the
`graduation-pathways` skill. The essentials:

- NJGPA is **dual-vendor**. `stg_pearson__njgpa` carries the retired form on a
  650-850 scale with a cut of 725, through the Fall 2025 administration.
  `stg_cambium__njgpa` carries the adaptive **NJGPA-A** on a 300-562 scale with
  a cut of 450, from Spring 2026 onward. Both report the same `assessment_name`
  and the same `testcode`.
- `assessment_version` is what tells them apart, set as a literal in each
  vendor's staging model and carried up through `int_pearson__all_assessments`.
- Cut scores live in a hand-maintained Google Sheet
  (`stg_google_sheets__student_graduation_path_cutoffs`), keyed on `cohort` +
  `discipline` + `score_type` + `assessment_version`.
- `cohort` is frozen at high school entry, which is correct for NJ's 4-year
  adjusted cohort graduation rate but means a retained or accelerated student
  sits the assessment with a different class than their cohort.

### Transfer scores are entered by hand in PowerSchool

Transfer students' NJGPA scores do not arrive in a vendor file. School staff
enter them per instance at **District Management > Tests > Standardized Tests**,
then **Edit Scores**.

Both forms share one holder named `NJGPA/NJGPA-A`, type State, with four score
fields. `int_powerschool__state_assessments_transfer_scores` reads the version
off the `-A` suffix, then strips the suffix so the code still joins to the
sheet:

| Score field | `assessment_version` | `testcode` |
| ----------- | -------------------- | ---------- |
| `ELAGP`     | `NJGPA`              | `ELAGP`    |
| `MATGP`     | `NJGPA`              | `MATGP`    |
| `ELAGP-A`   | `NJGPA-A`            | `ELAGP`    |
| `MATGP-A`   | `NJGPA-A`            | `MATGP`    |

User guide, which **must be updated whenever transfer-score entry changes**:
[Adding NJGPA Scores to PowerSchool for Transfer Students](https://teamschools.zendesk.com/hc/en-us/articles/20823542157463--User-Guide-Adding-NJGPA-Scores-to-PowerSchool-for-Transfer-Students)

!!! warning "Paterson needs this configured first"

    Only the Newark and Camden PowerSchool instances have the `NJGPA/NJGPA-A`
    holder. Paterson has no NJGPA data at all today, so it contributes no rows —
    which is correct, not a defect.

    When Paterson first receives an NJGPA transfer score, its instance needs the
    same setup first: a standardized test named exactly `NJGPA/NJGPA-A`, type
    State, with all four score fields above. A score entered before the holder
    exists cannot be captured, and there is no error to notice — the model
    filters on the holder name, so a missing or differently-named holder simply
    yields zero rows.

    The score field names matter as much as the holder name. Anything outside
    `ELAGP` / `MATGP` / `ELAGP-A` / `MATGP-A` produces a testcode that matches no
    cut score row; the `accepted_values` test on `testcode` turns that into a
    build failure rather than a silently dropped score.
