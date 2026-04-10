select
    b._dbt_source_relation,
    b.schoolid,
    b.yearid,
    b.academic_year,
    b.`quarter`,
    b.semester,
    b.quarter_start_date,
    b.quarter_end_date,
    b.is_current_term,
    b.school,
    b.region,
    b.school_level,
    b.region_school_level,
    b.week_start_date,
    b.week_end_date,
    b.week_start_monday,
    b.week_end_sunday,
    b.school_week_start_date_lead,
    b.week_number_academic_year,
    b.week_number_quarter,
    b.is_current_week,
    b.academic_year_display,
    b.quarter_end_date_insession,
    b.sections_dcid,
    b.sectionid,
    b.section_number,
    b.external_expression,
    b.course_number,
    b.course_name,
    b.credit_type,
    b.exclude_from_gpa,
    b.is_ap_course,
    b.teacher_number,
    b.teacher_name,
    b.teacher_tableau_username,
    b.hos,
    b.school_leader,
    b.school_leader_tableau_username,
    b.is_quarter_end_date_range,
    b.section_or_period,
    b.assignment_category_term,
    b.expectation,
    b.notes,

    a.category_code as assignment_category_code,
    a.category_name as assignment_category_name,
    a.name as assignment_name,
    a.duedate as due_date,
    a.scoretype as score_type,
    a.totalpointvalue as max_score,

    a.whocreated as created_by,
    a.whencreated as create_date,
    a.whomodified as modified_by,
    a.whenmodified as modify_date,

    a.publisheddate as published_date,
    a.transaction_date as date_ps_detected_updates,

    if(a.iscountedinfinalgrade = 1, true, false) as is_counted_final_grade,

from {{ ref("int_tableau__gradebook_audit_section_week_scaffold") }} as b
inner join
    {{ ref("int_powerschool__gradebook_assignments") }} as a
    on b.sections_dcid = a.sectionsdcid
    and a.duedate between b.week_start_monday and b.week_end_sunday
    and {{ union_dataset_join_clause(left_alias="b", right_alias="a") }}
where b.region_school_level not in ('CamdenES', 'NewarkES')
