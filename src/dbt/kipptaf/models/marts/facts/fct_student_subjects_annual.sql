with
    subjects as (
        select
            discipline,

            case
                discipline when 'ELA' then 'Text Study' when 'Math' then 'Mathematics'
            end as illuminate_subject_area,
        from unnest(['ELA', 'Math']) as discipline
    ),

    -- the primary stint: one row per student and year
    enrollments as (
        select
            student_number,
            academic_year,
            _dbt_source_project,

            -- Florida state scores are keyed on the Florida Education Identifier
            if(
                _dbt_source_project = 'kippmiami', fleid, state_studentnumber
            ) as state_test_student_id,
        from {{ ref("int_students__student_enrollments") }}
        where rn_year = 1
    ),

    dibels_composite as (
        select student_number, academic_year, proficiency_level,
        from {{ ref("int_assessments__benchmark_scores") }}
        where
            is_latest_in_year
            and module_code = 'Composite'
            and response_type = 'overall'
    )

select
    enr.academic_year,

    sj.discipline,

    db.proficiency_level as latest_dibels_composite_level,

    {{
        dbt_utils.generate_surrogate_key(
            ["enr.student_number", "enr.academic_year", "sj.discipline"]
        )
    }} as student_subject_annual_key,

    {{ student_key("enr.student_number") }} as student_key,

    coalesce(py.aggregated_proficiency, 'No Test') as prior_year_state_test_proficiency,

    -- Low 25: below the 25.5th percentile on last spring's FAST PM3
    if(fp.fldoe_dynamic_percentile_rank < .255, true, false) as is_prior_year_low_25,
from enrollments as enr
cross join subjects as sj
left join
    {{ ref("int_assessments__state_scores") }} as py
    on enr.state_test_student_id = py.state_student_id
    and enr.academic_year = py.benchmark_academic_year
    and enr._dbt_source_project = py._dbt_source_project
    and sj.illuminate_subject_area = py.illuminate_subject_area
    and py.is_annual_state_test
left join
    {{ ref("int_assessments__fast_previous_year") }} as fp
    on enr.student_number = fp.student_number
    and enr.academic_year = fp.academic_year
    and enr._dbt_source_project = fp._dbt_source_project
    and sj.discipline = fp.discipline
left join
    dibels_composite as db
    on enr.student_number = db.student_number
    and enr.academic_year = db.academic_year
    and sj.discipline = 'ELA'
