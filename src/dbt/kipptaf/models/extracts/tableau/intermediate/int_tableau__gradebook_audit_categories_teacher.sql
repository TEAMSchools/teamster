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

    assignment_aggs as (
        select
            sec._dbt_source_relation,
            sec.sectionid,
            sec.`quarter`,
            sec.week_number_quarter,
            sec.assignment_category_code,
            sec.assignment_category_term,

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
                    sec.`quarter`,
                    sec.sectionid,
                    sec.assignment_category_code
            ) as sum_totalpointvalue_section_quarter_category,

            sum(asg.n_expected) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sectionid,
                    sec.`quarter`,
                    sec.week_number_quarter,
                    sec.assignment_category_code
            ) as total_expected_section_quarter_week_category,

            sum(asg.n_expected_scored) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sectionid,
                    sec.`quarter`,
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
            assignment_score_rollup as asg
            on a.assignmentsectionid = asg.assignmentsectionid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="asg") }}
    ),

    category_aggs as (
        select
            _dbt_source_relation,
            sectionid,
            `quarter`,
            week_number_quarter,
            assignment_category_code,

            max(
                teacher_running_total_assign_by_cat
            ) as teacher_running_total_assign_by_cat,
            max(
                sum_totalpointvalue_section_quarter_category
            ) as sum_totalpointvalue_section_quarter_category,
            max(
                total_expected_section_quarter_week_category
            ) as total_expected_section_quarter_week_category,
            max(
                total_expected_scored_section_quarter_week_category
            ) as total_expected_scored_section_quarter_week_category,

        from assignment_aggs
        group by
            _dbt_source_relation,
            sectionid,
            `quarter`,
            week_number_quarter,
            assignment_category_code
    ),

    final as (
        select
            sec.* except (expectation),

            cast(sec.expectation as float64) as expectation,
            cast(
                agg.teacher_running_total_assign_by_cat as float64
            ) as teacher_running_total_assign_by_cat,
            agg.sum_totalpointvalue_section_quarter_category,
            cast(
                agg.total_expected_section_quarter_week_category as float64
            ) as total_expected_section_quarter_week_category,
            cast(
                agg.total_expected_scored_section_quarter_week_category as float64
            ) as total_expected_scored_section_quarter_week_category,

            safe_divide(
                agg.total_expected_scored_section_quarter_week_category,
                agg.total_expected_section_quarter_week_category
            ) as percent_graded_for_quarter_week_class,

        from
            {{ ref("int_tableau__gradebook_audit_section_week_category_scaffold") }}
            as sec
        left join
            category_aggs as agg
            on sec._dbt_source_relation = agg._dbt_source_relation
            and sec.sectionid = agg.sectionid
            and sec.quarter = agg.quarter
            and sec.week_number_quarter = agg.week_number_quarter
            and sec.assignment_category_code = agg.assignment_category_code
    )

select
    f._dbt_source_relation,
    f.schoolid,
    f.yearid,
    f.academic_year,
    f.`quarter`,
    f.semester,
    f.quarter_start_date,
    f.quarter_end_date,
    f.is_current_term,
    f.school,
    f.region,
    f.school_level,
    f.region_school_level,
    f.week_start_date,
    f.week_end_date,
    f.week_start_monday,
    f.week_end_sunday,
    f.school_week_start_date_lead,
    f.week_number_academic_year,
    f.week_number_quarter,
    f.is_current_week,
    f.academic_year_display,
    f.quarter_end_date_insession,
    f.sections_dcid,
    f.sectionid,
    f.section_number,
    f.external_expression,
    f.course_number,
    f.course_name,
    f.credit_type,
    f.exclude_from_gpa,
    f.is_ap_course,
    f.teacher_number,
    f.teacher_name,
    f.teacher_tableau_username,
    f.hos,
    f.school_leader,
    f.school_leader_tableau_username,
    f.is_quarter_end_date_range,
    f.section_or_period,
    f.assignment_category_code,
    f.assignment_category_name,
    f.assignment_category_term,
    f.expectation,
    f.notes,
    f.teacher_running_total_assign_by_cat,
    f.sum_totalpointvalue_section_quarter_category,
    f.total_expected_section_quarter_week_category,
    f.total_expected_scored_section_quarter_week_category,
    f.percent_graded_for_quarter_week_class,

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
