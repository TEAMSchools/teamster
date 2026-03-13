with
    course_enrollments as (
        select
            c._dbt_source_relation,
            c.cc_academic_year as academic_year,
            c.students_student_number as student_number,
            c.courses_credittype,
            c.teachernumber,
            c.teacher_lastfirst as teacher_name,
            c.courses_course_name as course_name,
            c.cc_course_number as course_number,

            s.abbreviation as school,

            case
                c.courses_credittype
                when 'ENG'
                then 'ELA'
                when 'MATH'
                then 'Math'
                when 'SCI'
                then 'Science'
                when 'SOC'
                then 'Civics'
            end as discipline,

        from {{ ref("base_powerschool__course_enrollments") }} as c
        left join
            {{ ref("stg_powerschool__schools") }} as s
            on c.cc_schoolid = s.school_number
        where
            c.cc_academic_year >= {{ var("current_academic_year") - 7 }}
            and c.rn_credittype_year = 1
            and not c.is_dropped_section
            and c.courses_credittype in ('ENG', 'MATH', 'SCI', 'SOC')
    )

select
    ce._dbt_source_relation,
    ce.academic_year,
    ce.student_number,
    ce.discipline,
    ce.teachernumber,
    ce.teacher_name,
    ce.course_number,
    ce.course_name,
    ce.school,

    sf.nj_student_tier as student_tier,
    sf.is_tutoring,

    sf_prev.iready_proficiency_eoy,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "ce._dbt_source_relation",
                "ce.student_number",
                "ce.academic_year",
                "ce.discipline",
            ]
        )
    }} as student_course_enrollments_key,

from course_enrollments as ce
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as sf
    on ce.academic_year = sf.academic_year
    and ce.discipline = sf.discipline
    and ce.student_number = sf.student_number
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="sf") }}
    and sf.rn_year = 1
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as sf_prev
    on (ce.academic_year - 1) = sf_prev.academic_year
    and ce.discipline = sf_prev.discipline
    and ce.student_number = sf_prev.student_number
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="sf_prev") }}
    and sf_prev.rn_year = 1
