with
    assignment_score_rollup as (
        select
            _dbt_source_relation,
            assignmentsectionid,

            count(students_dcid) as n_students,

            sum(is_expected_late) as n_late,
            sum(is_exempt) as n_exempt,
            sum(is_expected_missing) as n_missing,
            sum(is_expected_null) as n_null,
            sum(is_expected_academic_dishonesty) as n_academic_dishonesty,

            sum(
                if(is_expected_null = 1 and is_expected_missing = 1, 1, 0)
            ) as n_is_null_missing,

            sum(
                if(is_expected_null = 1 and is_expected_missing = 0, 1, 0)
            ) as n_is_null_not_missing,

            countif(is_expected) as n_expected,
            countif(is_expected_scored) as n_expected_scored,

            avg(
                if(is_expected_scored, assign_final_score_percent, null)
            ) as teacher_avg_score_for_assign_per_class_section_and_assign_id,

        from {{ ref("int_powerschool__gradebook_assignments_scores") }}
        group by _dbt_source_relation, assignmentsectionid
    )

select
    sec.*,

    a.assignmentsectionid,
    a.assignmentid,
    a.name as assignment_name,
    a.duedate,
    a.scoretype,
    a.totalpointvalue,

    if(e.include_row is null, asg.n_students, null) as n_students,
    if(e.include_row is null, asg.n_late, null) as n_late,
    if(e.include_row is null, asg.n_exempt, null) as n_exempt,
    if(e.include_row is null, asg.n_missing, null) as n_missing,
    if(e.include_row is null, asg.n_academic_dishonesty, null) as n_academic_dishonesty,
    if(e.include_row is null, asg.n_null, null) as n_null,
    if(e.include_row is null, asg.n_is_null_missing, null) as n_is_null_missing,
    if(e.include_row is null, asg.n_is_null_not_missing, null) as n_is_null_not_missing,
    if(e.include_row is null, asg.n_expected, null) as n_expected,
    if(e.include_row is null, asg.n_expected_scored, null) as n_expected_scored,
    if(
        e.include_row is null,
        asg.teacher_avg_score_for_assign_per_class_section_and_assign_id,
        null
    ) as teacher_avg_score_for_assign_per_class_section_and_assign_id,

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
    ) as teacher_running_total_assign_by_cat,

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
-- temporarily remove rows for assignmnent_rollup calcs during non-eoq times
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
    on sec.academic_year = e.academic_year
    and sec.region = e.region
    and sec.course_number = e.course_number
    and sec.is_quarter_end_date_range = e.is_quarter_end_date_range
    and e.view_name = 'assignments_teacher'
    and e.cte is null
    and e.course_number is not null
    and e.is_quarter_end_date_range is not null
where sec.scaffold_name = 'teacher_category_scaffold'
