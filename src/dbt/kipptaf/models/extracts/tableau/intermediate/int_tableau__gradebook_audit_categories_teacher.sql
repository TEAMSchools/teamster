with
    assignments as (
        select
            sec.*,

            count(a.assignmentid) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sectionid,
                    sec.assignment_category_term
                order by sec.week_number_quarter asc
            ) as running_count_assignments_section_category_term,

            sum(a.totalpointvalue) over (
                partition by
                    sec._dbt_source_relation,
                    sec.quarter,
                    sec.sectionid,
                    sec.assignment_category_code
            ) as sum_totalpointvalue_section_quarter_category,

            sum(asg.n_expected) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sectionid,
                    sec.quarter,
                    sec.week_number_quarter,
                    sec.assignment_category_code
            ) as total_expected_section_quarter_week_category,

            sum(asg.n_expected_scored) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sectionid,
                    sec.quarter,
                    sec.week_number_quarter,
                    sec.assignment_category_code
            ) as total_expected_scored_section_quarter_week_category,

        from
            {{ ref("int_tableau__gradebook_audit_section_week_category_scaffold") }}
            as sec
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
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on sec.academic_year = e1.academic_year
            and sec.region = e1.region
            and sec.school_level = e1.school_level
            and sec.course_number = e1.course_number
            and e1.view_name = 'int_tableau__gradebook_audit_categories_teacher'
            and e1.credit_type is null
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on sec.academic_year = e2.academic_year
            and sec.region = e2.region
            and sec.school_level = e2.school_level
            and sec.credit_type = e2.credit_type
            and e2.view_name = 'int_tableau__gradebook_audit_categories_teacher'
            and e2.credit_type is not null
        where e1.`include` is null and e2.`include` is null
    ),

    percent_graded as (
        select
            *,

            safe_divide(
                total_expected_scored_section_quarter_week_category,
                total_expected_section_quarter_week_category
            ) as percent_graded_for_quarter_week_class,

        from assignments
    ),

    final as (
        select
            _dbt_source_relation,
            schoolid,
            yearid,
            academic_year,
            quarter,
            semester,
            quarter_start_date,
            quarter_end_date,
            is_current_term,
            school,
            region,
            school_level,
            region_school_level,
            week_start_date,
            week_end_date,
            week_start_monday,
            week_end_sunday,
            school_week_start_date_lead,
            week_number_academic_year,
            week_number_quarter,
            academic_year_display,
            quarter_end_date_insession,
            sections_dcid,
            sectionid,
            section_number,
            external_expression,
            course_number,
            course_name,
            credit_type,
            exclude_from_gpa,
            is_ap_course,
            teacher_number,
            teacher_name,
            teacher_tableau_username,
            hos,
            school_leader,
            school_leader_tableau_username,
            is_quarter_end_date_range,
            section_or_period,
            assignment_category_code,
            assignment_category_name,
            assignment_category_term,
            notes,

            avg(expectation) as expectation,

            avg(
                running_count_assignments_section_category_term
            ) as running_count_assignments_section_category_term,

            avg(
                sum_totalpointvalue_section_quarter_category
            ) as sum_totalpointvalue_section_quarter_category,

            avg(
                total_expected_section_quarter_week_category
            ) as total_expected_section_quarter_week_category,

            avg(
                total_expected_scored_section_quarter_week_category
            ) as total_expected_scored_section_quarter_week_category,

            avg(
                percent_graded_for_quarter_week_class
            ) as percent_graded_for_quarter_week_class,

        from percent_graded
        group by all
    )

select
    *,

    if(
        assignment_category_code = 'W' and percent_graded_for_quarter_week_class < .7,
        true,
        false
    ) as w_percent_graded_min_not_met,

    if(
        assignment_category_code = 'F' and percent_graded_for_quarter_week_class < .7,
        true,
        false
    ) as f_percent_graded_min_not_met,

    if(
        assignment_category_code = 'S' and percent_graded_for_quarter_week_class < .7,
        true,
        false
    ) as s_percent_graded_min_not_met,

    if(
        assignment_category_code = 'W'
        and running_count_assignments_section_category_term < expectation,
        true,
        false
    ) as w_expected_assign_count_not_met,

    if(
        assignment_category_code = 'F'
        and running_count_assignments_section_category_term < expectation,
        true,
        false
    ) as f_expected_assign_count_not_met,

    if(
        assignment_category_code = 'S'
        and running_count_assignments_section_category_term < expectation,
        true,
        false
    ) as s_expected_assign_count_not_met,

    if(
        assignment_category_code = 'S'
        and region_school_level != 'MiamiES'
        and sum_totalpointvalue_section_quarter_category > 200,
        true,
        false
    ) as qt_teacher_s_total_greater_200,

    if(
        assignment_category_code = 'S'
        and region_school_level != 'MiamiES'
        and sum_totalpointvalue_section_quarter_category < 200,
        true,
        false
    ) as qt_teacher_s_total_less_200,

    if(
        assignment_category_code = 'S'
        and region_school_level = 'MiamiES'
        and sum_totalpointvalue_section_quarter_category > 100,
        true,
        false
    ) as qt_teacher_s_total_greater_100,

    if(
        assignment_category_code = 'S'
        and region_school_level = 'MiamiES'
        and sum_totalpointvalue_section_quarter_category < 100,
        true,
        false
    ) as qt_teacher_s_total_less_100,

from final
