with
    school_course_exceptions as (
        select s._dbt_source_relation, s.sections_dcid, e.`include`,
        from {{ ref("base_powerschool__sections") }} as s
        inner join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on s.terms_academic_year = e.academic_year
            and s.sections_schoolid = e.school_id
            and s.sections_course_number = e.course_number
            and e.view_name = 'int_powerschool__assignment_score_rollup'
            and e.cte = 'school_course_exceptions'
            and e.course_number is not null
            and e.is_quarter_end_date_range is null

        union all

        select s._dbt_source_relation, s.sections_dcid, e.`include`,
        from {{ ref("base_powerschool__sections") }} as s
        inner join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on s.terms_academic_year = e.academic_year
            and s.sections_schoolid = e.school_id
            and s.courses_credittype = e.credit_type
            and e.view_name = 'int_powerschool__assignment_score_rollup'
            and e.cte = 'school_course_exceptions'
            and e.credit_type is not null
            and e.is_quarter_end_date_range is null

        union all

        select s._dbt_source_relation, s.sections_dcid, e.`include`,
        from {{ ref("base_powerschool__sections") }} as s
        inner join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on s.terms_academic_year = e.academic_year
            and s.sections_course_number = e.course_number
            and e.view_name = 'int_powerschool__assignment_score_rollup'
            and e.cte = 'school_course_exceptions'
            and e.course_number is not null
            and e.is_quarter_end_date_range is not null
    )

select
    s._dbt_source_relation,
    s.assignmentsectionid,

    count(s.students_dcid) as n_students,

    sum(s.is_expected_late) as n_late,
    sum(s.is_exempt) as n_exempt,
    sum(s.is_expected_missing) as n_missing,
    sum(s.is_expected_null) as n_null,

    sum(
        if(s.is_expected_null = 1 and s.is_expected_missing = 1, 1, 0)
    ) as n_is_null_missing,

    sum(
        if(s.is_expected_null = 1 and s.is_expected_missing = 0, 1, 0)
    ) as n_is_null_not_missing,

    countif(s.is_expected) as n_expected,
    countif(s.is_expected_scored) as n_expected_scored,

    avg(
        if(s.is_expected_scored, s.assign_final_score_percent, null)
    ) as avg_expected_scored_percent,

from {{ ref("int_powerschool__gradebook_assignments_scores") }} as s
left join
    school_course_exceptions as e1
    on s.sectionsdcid = e1.sections_dcid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="e1") }}
where e1.`include` is null
group by s._dbt_source_relation, s.assignmentsectionid
