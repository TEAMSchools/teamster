with
    category_grades as (
        select
            _dbt_source_relation,
            yearid,
            studentid,
            sectionid,
            storecode,
            percent_grade,

            round(
                avg(percent_grade) over (
                    partition by _dbt_source_relation, studentid, yearid, storecode
                ),
                2
            ) as category_quarter_average_all_courses,

        from {{ ref("int_powerschool__category_grades") }}
        where
            yearid = {{ var("current_academic_year") - 1991 }}
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')
    )

select
    s.*,

    ge.assignment_category_name,
    ge.assignment_category_code,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    cg.percent_grade as category_quarter_percent_grade,
    cg.category_quarter_average_all_courses,

    if(
        ge.assignment_category_code = 'W'
        and s.school_level != 'ES'
        and abs(
            round(cg.category_quarter_average_all_courses, 2)
            - round(cg.percent_grade, 2)
        )
        >= 30,
        true,
        false
    ) as w_grade_inflation,

    if(
        s.region = 'Miami'
        and ge.assignment_category_code = 'W'
        and cg.percent_grade is null
        and s.is_quarter_end_date_range,
        true,
        false
    ) as qt_effort_grade_missing,

    if(
        s.region = 'Miami'
        and s.school_level = 'ES'
        and ge.assignment_category_code = 'F'
        and cg.percent_grade is null
        and s.is_quarter_end_date_range,
        true,
        false
    ) as qt_formative_grade_missing,

    if(
        s.region = 'Miami'
        and s.school_level = 'ES'
        and s.credit_type not in ('ENG', 'MATH')
        and ge.assignment_category_code = 'S'
        and cg.percent_grade is null
        and s.is_quarter_end_date_range,
        true,
        false
    ) as qt_summative_grade_missing,

from {{ ref("int_tableau__gradebook_audit_section_week_student_scaffold") }} as s
inner join
    {{ ref("stg_reporting__gradebook_expectations") }} as ge
    on s.region = ge.region
    and s.school_level = ge.school_level
    and s.academic_year = ge.academic_year
    and s.quarter = ge.quarter
    and s.week_number_quarter = ge.week_number
left join
    category_grades as cg
    on s.studentid = cg.studentid
    and s.yearid = cg.yearid
    and s.sectionid = cg.sectionid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="cg") }}
    and ge.assignment_category_term = cg.storecode
