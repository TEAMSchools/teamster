with
    exceptions as (
        select s._dbt_source_relation, s.sections_dcid, e.include_row,
        from {{ ref("base_powerschool__sections") }} as s
        inner join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on s.terms_academic_year = e.academic_year
            and s.sections_schoolid = e.school_id
            and s.sections_course_number = e.course_number
            and e.view_name = 'assignments_teacher'
            and e.cte = 'school_course_exceptions'
            and e.course_number is not null
            and e.is_quarter_end_date_range is null

        union all

        select s._dbt_source_relation, s.sections_dcid, e.include_row,
        from {{ ref("base_powerschool__sections") }} as s
        inner join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on s.terms_academic_year = e.academic_year
            and s.sections_schoolid = e.school_id
            and s.courses_credittype = e.credit_type
            and e.view_name = 'assignments_teacher'
            and e.cte = 'school_course_exceptions'
            and e.credit_type is not null
            and e.is_quarter_end_date_range is null

        union all

        select s._dbt_source_relation, s.sections_dcid, e.include_row,
        from {{ ref("base_powerschool__sections") }} as s
        inner join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on s.terms_academic_year = e.academic_year
            and s.sections_course_number = e.course_number
            and e.view_name = 'assignments_teacher'
            and e.cte = 'school_course_exceptions'
            and e.course_number is not null
            and e.is_quarter_end_date_range is not null
    ),

    assignment_score_rollup as (
        select
            s._dbt_source_relation,
            s.assignmentsectionid,

            count(s.students_dcid) as n_students,

            sum(s.is_expected_late) as n_late,
            sum(s.is_exempt) as n_exempt,
            sum(s.is_expected_missing) as n_missing,
            sum(s.is_expected_null) as n_null,
            sum(s.is_expected_academic_dishonesty) as n_academic_dishonesty,

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
            exceptions as e
            on s.sectionsdcid = e.sections_dcid
            and {{ union_dataset_join_clause(left_alias="s", right_alias="e") }}
        where e.include_row is null
        group by s._dbt_source_relation, s.assignmentsectionid
    )

select
    sec.*,

    a.assignmentsectionid,
    a.assignmentid,
    a.name as assignment_name,
    a.duedate,
    a.scoretype,
    a.totalpointvalue,

    asg.n_students,
    asg.n_late,
    asg.n_exempt,
    asg.n_missing,
    asg.n_academic_dishonesty,
    asg.n_null,
    asg.n_is_null_missing,
    asg.n_is_null_not_missing,
    asg.n_expected,
    asg.n_expected_scored,
    asg.avg_expected_scored_percent,

    if(
        sec.assignment_category_code = 'W' and a.totalpointvalue != 10, true, false
    ) as w_assign_max_score_not_10,

    if(
        sec.assignment_category_code = 'F' and a.totalpointvalue != 10, true, false
    ) as f_assign_max_score_not_10,

    if(
        sec.assignment_category_code = 'H'
        and sec.school_level != 'ES'
        and a.totalpointvalue != 10,
        true,
        false
    ) as h_assign_max_score_not_10,

    if(
        sec.region = 'Miami'
        and sec.assignment_category_code = 'S'
        and a.totalpointvalue > 100,
        true,
        false
    ) as s_max_score_greater_100,

    sum(a.totalpointvalue) over (
        partition by
            sec._dbt_source_relation,
            sec.quarter,
            sec.sectionid,
            sec.assignment_category_code
    ) as sum_totalpointvalue_section_quarter_category,

    count(a.assignmentid) over (
        partition by
            sec._dbt_source_relation, sec.sectionid, sec.assignment_category_term
        order by sec.week_number_quarter asc
    ) as running_count_assignments_section_category_term,

from {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as sec
left join
    {{ ref("int_powerschool__gradebook_assignments") }} as a
    on sec.sections_dcid = a.sectionsdcid
    and sec.assignment_category_name = a.category_name
    and a.duedate between sec.week_start_monday and sec.week_end_sunday
    and {{ union_dataset_join_clause(left_alias="sec", right_alias="a") }}
left join
    assignment_score_rollup as asg
    on a.assignmentsectionid = asg.assignmentsectionid
    and {{ union_dataset_join_clause(left_alias="a", right_alias="asg") }}
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
    on sec.academic_year = e1.academic_year
    and sec.region = e1.region
    and sec.school_level = e1.school_level
    and sec.course_number = e1.course_number
    and e1.view_name = 'assignments_teacher'
    and e1.is_quarter_end_date_range is null
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
    on sec.academic_year = e2.academic_year
    and sec.region = e2.region
    and sec.course_number = e2.course_number
    and sec.is_quarter_end_date_range = e2.is_quarter_end_date_range
    and e2.view_name = 'assignments_teacher'
    and e2.is_quarter_end_date_range is not null
where
    sec.scaffold_name = 'teacher_category_scaffold'
    and e1.include_row is null
    and e2.include_row is null
