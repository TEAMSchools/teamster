with
    assignment_score_rollup as (
        select
            s._dbt_source_relation,
            s.assignmentsectionid,

            countif(s.is_expected) as n_expected,
            countif(s.is_expected_scored) as n_expected_scored,

        from {{ ref("int_powerschool__gradebook_assignments_scores") }} as s
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on s.academic_year = e1.academic_year
            and s.region = e1.region
            and s.school_level = e1.school_level
            and s.credit_type = e1.credit_type
            and e1.view_name = 'categories_teacher'
            and e1.cte = 'assignment_score_rollup'
            and e1.credit_type is not null
        where e1.include_row is null
        group by s._dbt_source_relation, s.assignmentsectionid
    ),

    assignments as (
        select
            sec.*,

            count(a.assignmentid) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sectionid,
                    sec.assignment_category_term
                order by sec.week_number_quarter asc
            ) as teacher_running_total_assign_by_cat,

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
        where sec.scaffold_name = 'teacher_category_scaffold'
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
            is_current_week,
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
                teacher_running_total_assign_by_cat
            ) as teacher_running_total_assign_by_cat,

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
        group by
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
            is_current_week,
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
            notes
    )

select
    f.*,

    if(
        f.assignment_category_code = 'W'
        and f.percent_graded_for_quarter_week_class < .7,
        true,
        false
    ) as w_percent_graded_min_not_met,

    if(
        f.assignment_category_code = 'H'
        and f.percent_graded_for_quarter_week_class < .7,
        true,
        false
    ) as h_percent_graded_min_not_met,

    if(
        f.assignment_category_code = 'F'
        and f.percent_graded_for_quarter_week_class < .7,
        true,
        false
    ) as f_percent_graded_min_not_met,

    if(
        f.assignment_category_code = 'S'
        and f.percent_graded_for_quarter_week_class < .7,
        true,
        false
    ) as s_percent_graded_min_not_met,

    if(
        f.assignment_category_code = 'W'
        and f.teacher_running_total_assign_by_cat < f.expectation,
        true,
        false
    ) as w_expected_assign_count_not_met,

    if(
        f.assignment_category_code = 'H'
        and f.teacher_running_total_assign_by_cat < f.expectation,
        true,
        false
    ) as h_expected_assign_count_not_met,

    if(
        f.assignment_category_code = 'F'
        and f.teacher_running_total_assign_by_cat < f.expectation,
        true,
        false
    ) as f_expected_assign_count_not_met,

    if(
        f.assignment_category_code = 'S'
        and f.teacher_running_total_assign_by_cat < f.expectation,
        true,
        false
    ) as s_expected_assign_count_not_met,

    if(
        f.assignment_category_code = 'S'
        and f.region_school_level != 'MiamiES'
        and f.sum_totalpointvalue_section_quarter_category > 200,
        true,
        false
    ) as qt_teacher_s_total_greater_200,

    if(
        f.assignment_category_code = 'S'
        and f.region_school_level != 'MiamiES'
        and f.sum_totalpointvalue_section_quarter_category < 200,
        true,
        false
    ) as qt_teacher_s_total_less_200,

    if(
        f.assignment_category_code = 'S'
        and f.region_school_level = 'MiamiES'
        and f.sum_totalpointvalue_section_quarter_category > 100,
        true,
        false
    ) as qt_teacher_s_total_greater_100,

    if(
        f.assignment_category_code = 'S'
        and f.region_school_level = 'MiamiES'
        and f.sum_totalpointvalue_section_quarter_category < 100,
        true,
        false
    ) as qt_teacher_s_total_less_100,

from final as f
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
    on f.academic_year = e.academic_year
    and f.region = e.region
    and f.course_number = e.course_number
    and f.is_quarter_end_date_range = e.is_quarter_end_date_range
    and e.view_name = 'categories_teacher'
    and e.cte is null
    and e.is_quarter_end_date_range is not null
where e.include_row is null
