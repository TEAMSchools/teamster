with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_cambium", model.name),
                    source("kippcamden_cambium", model.name),
                ]
            )
        }}
    )

select
    /* _dbt_source_relation is in the union's include list and every existing
       relation carries it. It is only READ inside extract_source_project, so it
       is easy to forget to select -- which would null-fill it for all 813 rows
       and break the _dbt_source_relation / _dbt_source_project pairing
       invariant in kipptaf/CLAUDE.md. */
    _dbt_source_relation,
    asian,
    academic_year,
    /* Genuinely NULL from Cambium. NOT synthesized -- the single consumer
       coalesces instead. See design spec D2. */
    test_score_complete as testscorecomplete,
    assessment_grade as assessmentgrade,
    assessment_year as assessmentyear,
    american_indian_or_alaska_native as americanindianoralaskanative,
    black_or_african_american as blackorafricanamerican,
    first_name as firstname,
    hispanic_or_latino_ethnicity as hispanicorlatinoethnicity,
    last_or_surname as lastorsurname,
    local_student_identifier as localstudentidentifier,
    multilingual_learner as englishlearnerel,
    native_hawaiian_or_other_pacific_islander as nativehawaiianorotherpacificislander,
    `period`,
    state_student_identifier as statestudentidentifier,
    student_test_uuid as studenttestuuid,
    student_with_disabilities as studentwithdisabilities,
    `subject`,
    test_code as testcode,
    test_code as module_code,
    test_date,
    test_performance_level as testperformancelevel,
    test_scale_score as testscalescore,
    two_or_more_races as twoormoreraces,
    white,

    'NJGPA' as assessment_name,

    /* NJGPA's reported grade is 11 across all Pearson history -- 4,130 rows,
       fall retakers in 12th grade included. Neither Cambium field reproduces
       that: assessment_grade is the test DESIGN level (10 for ELA, 11 for
       Math) and grade_level_when_assessed is the student's grade (11 or 12).
       So the value is asserted, keyed on test_code rather than written as a
       bare literal, so an unrecognized code yields NULL instead of a
       confident 11. Asserting 11 also keeps dim_assessments deterministic:
       its dedup tiebreaker is `title` (the constant 'NJGPA'), which cannot
       choose between two candidate grade levels for the ELAGP row. */
    case test_code when 'ELAGP' then 11 when 'MATGP' then 11 end as test_grade,

    if(`subject` = 'Mathematics', 'Math', 'ELA') as discipline,

    if(
        `subject` = 'English Language Arts/Literacy', 'English Language Arts', `subject`
    ) as subject_area,

    /* Case-insensitive, unlike the Pearson model's exact FallBlock match.
       The fall token has drifted historically (FallBlock in 2024, FALL in
       2025). An exact match would leave 'FALL' as-is, which creates a SEPARATE
       dim_assessment_administrations tuple from the Pearson 'Fall' rows and
       splits the Fall series on the dashboard -- invisibly, because the
       resolver joins the same value on both sides so nothing errors. */
    if(upper(`period`) like 'FALL%', 'Fall', `period`) as administration_period,

    if(test_performance_level = 2, true, false) as is_proficient,

    case
        test_performance_level
        when 2
        then 'Graduation Ready'
        when 1
        then 'Not Yet Graduation Ready'
    end as testperformancelevel_text,

    {{ extract_source_project("union_relations") }} as _dbt_source_project,

from union_relations
