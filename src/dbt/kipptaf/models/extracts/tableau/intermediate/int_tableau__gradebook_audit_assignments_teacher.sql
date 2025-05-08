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
        sec.region = 'Miami'
        and sec.assignment_category_code = 'S'
        and a.totalpointvalue > 100,
        true,
        false
    ) as s_max_score_greater_100,

    count(a.assignmentid) over (
        partition by
            sec._dbt_source_relation, sec.sectionid, sec.assignment_category_term
        order by sec.week_number_quarter asc
    ) as running_count_assignments_section_category_term,

    sum(a.totalpointvalue) over (
        partition by
            sec._dbt_source_relation,
            sec.quarter,
            sec.sectionid,
            sec.assignment_category_code
    ) as sum_totalpointvalue_section_quarter_category,

from {{ ref("int_tableau__gradebook_audit_section_week_category_scaffold") }} as sec
left join
    {{ ref("int_powerschool__gradebook_assignments") }} as a
    on sec.sections_dcid = a.sectionsdcid
    and sec.assignment_category_name = a.category_name
    and a.duedate between sec.week_start_monday and sec.week_end_sunday
    and {{ union_dataset_join_clause(left_alias="sec", right_alias="a") }}
left join
    {{ ref("int_powerschool__assignment_score_rollup") }} as asg
    on a.assignmentsectionid = asg.assignmentsectionid
    and {{ union_dataset_join_clause(left_alias="a", right_alias="asg") }}
where
    concat(sec.region_school_level, sec.course_number)
    not in ('MiamiESWRI01133G4', 'MiamiESWRI01134G5')
