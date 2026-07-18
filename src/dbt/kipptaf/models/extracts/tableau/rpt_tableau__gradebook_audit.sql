with
    category_join as (
        select
            s._dbt_source_project,
            s.academic_year,
            s.academic_year_display,
            s.region_school_level_alt as region_school_level,
            s.region,
            s.school_level_alt as school_level,
            s.schoolid,
            s.school,

            s.course_number,
            s.course_name,
            s.credit_type,
            s.exclude_from_gpa,
            s.sections_dcid,
            s.sectionid,
            s.section_number,
            s.external_expression,
            s.section_or_period,
            s.teacher_number,
            s.teacher_name,
            s.teacher_employee_number,
            s.school_leader,
            s.manager_employee_number,
            s.manager_name,
            s.hos,

            s.teacher_tableau_username,
            s.manager_tableau_username,
            s.school_leader_tableau_username,

            s.`quarter`,
            s.semester,
            s.quarter_start_date,
            s.quarter_end_date,
            s.is_current_quarter,

            ge.assignment_category_code,
            ge.assignment_category_name,
            ge.assignment_category_term,

            r.assignmentid,
            r.assignment_name,
            r.duedate,
            r.scoretype,
            r.totalpointvalue,
            r.assignment_has_flags,

            max(ge.expectation) over (
                partition by
                    s._dbt_source_project,
                    s.sectionid,
                    s.`quarter`,
                    ge.assignment_category_code
            ) as expectation,

            countif(r.duedate <= ge.week_end_sunday) over (
                partition by
                    s._dbt_source_project,
                    s.sectionid,
                    s.`quarter`,
                    ge.assignment_category_code
            ) as assignments_entered_count,

            countif(
                r.duedate <= ge.week_end_sunday and not r.assignment_has_flags
            ) over (
                partition by
                    s._dbt_source_project,
                    s.sectionid,
                    s.`quarter`,
                    ge.assignment_category_code
            ) as assignments_entered_count_no_flags,

        from {{ ref("int_extracts__course_schedule_by_term") }} as s
        inner join
            {{ ref("int_powerschool__u_expectations_qtd_unpivot") }} as ge
            on s.region = ge.region
            and s.school_level_alt = ge.school_level
            and s.academic_year = ge.academic_year
            and s.`quarter` = ge.`quarter`
        left join
            {{ ref("int_powerschool__gradebook_assignment_scores_rollup") }} as r
            on s._dbt_source_project = r._dbt_source_project
            and s.sections_dcid = r.sectionsdcid
            and ge.assignment_category_code = r.category_code
            and r.duedate between s.quarter_start_date and s.quarter_end_date
            and r.scoretype in ('POINTS', 'PERCENT')
        where
            s.academic_year = {{ var("current_academic_year") - 1 }}  /* summer toggle: see skill */
            and s.school_level_alt != 'ES'
            and s._dbt_source_project != 'kippmiami'
            and s.exclude_from_gpa = 0
    ),

    category_dedup as (
        {{
            dbt_utils.deduplicate(
                relation="category_join",
                partition_by="_dbt_source_project, sectionid, `quarter`, assignment_category_code",
                order_by="assignmentid desc",
            )
        }}
    ),

    category_summary as (
        select
            _dbt_source_project,
            academic_year,
            academic_year_display,
            region_school_level,
            region,
            school_level,
            schoolid,
            school,

            course_number,
            course_name,
            credit_type,
            exclude_from_gpa,
            sections_dcid,
            sectionid,
            section_number,
            external_expression,
            section_or_period,
            teacher_number,
            teacher_name,
            teacher_employee_number,
            school_leader,
            manager_employee_number,
            manager_name,
            hos,

            teacher_tableau_username,
            manager_tableau_username,
            school_leader_tableau_username,

            `quarter`,
            semester,
            quarter_start_date,
            quarter_end_date,
            is_current_quarter,

            assignment_category_code,
            assignment_category_name,
            assignment_category_term,
            expectation,
            assignments_entered_count,

            if(
                assignments_entered_count_no_flags < expectation, true, false
            ) as not_enough_assignments,

        from category_dedup
    ),

    assignment_detail as (
        select
            _dbt_source_project,
            academic_year,
            academic_year_display,
            region_school_level,
            region,
            school_level,
            schoolid,
            school,

            course_number,
            course_name,
            credit_type,
            exclude_from_gpa,
            sections_dcid,
            sectionid,
            section_number,
            external_expression,
            section_or_period,
            teacher_number,
            teacher_name,
            teacher_employee_number,
            school_leader,
            manager_employee_number,
            manager_name,
            hos,

            teacher_tableau_username,
            manager_tableau_username,
            school_leader_tableau_username,

            `quarter`,
            semester,
            quarter_start_date,
            quarter_end_date,
            is_current_quarter,

            assignment_category_code,
            assignment_category_name,
            assignment_category_term,

            assignmentid,
            assignment_name,
            duedate,
            scoretype,
            totalpointvalue,

        from category_join
        where assignment_has_flags
    ),

    combined as (
        select
            _dbt_source_project,
            academic_year,
            academic_year_display,
            region_school_level,
            region,
            school_level,
            schoolid,
            school,

            course_number,
            course_name,
            credit_type,
            exclude_from_gpa,
            sections_dcid,
            sectionid,
            section_number,
            external_expression,
            section_or_period,
            teacher_number,
            teacher_name,
            teacher_employee_number,
            school_leader,
            manager_employee_number,
            manager_name,
            hos,

            teacher_tableau_username,
            manager_tableau_username,
            school_leader_tableau_username,

            `quarter`,
            semester,
            quarter_start_date,
            quarter_end_date,
            is_current_quarter,

            assignment_category_code,
            assignment_category_name,
            assignment_category_term,
            expectation,
            assignments_entered_count,
            not_enough_assignments,

            cast(null as int64) as assignmentid,
            cast(null as string) as assignment_name,
            cast(null as date) as duedate,
            cast(null as string) as scoretype,
            cast(null as int64) as totalpointvalue,

            'category_summary' as row_type,

        from category_summary

        union all

        select
            _dbt_source_project,
            academic_year,
            academic_year_display,
            region_school_level,
            region,
            school_level,
            schoolid,
            school,

            course_number,
            course_name,
            credit_type,
            exclude_from_gpa,
            sections_dcid,
            sectionid,
            section_number,
            external_expression,
            section_or_period,
            teacher_number,
            teacher_name,
            teacher_employee_number,
            school_leader,
            manager_employee_number,
            manager_name,
            hos,

            teacher_tableau_username,
            manager_tableau_username,
            school_leader_tableau_username,

            `quarter`,
            semester,
            quarter_start_date,
            quarter_end_date,
            is_current_quarter,

            assignment_category_code,
            assignment_category_name,
            assignment_category_term,
            cast(null as int64) as expectation,
            cast(null as int64) as assignments_entered_count,
            cast(null as bool) as not_enough_assignments,

            assignmentid,
            assignment_name,
            duedate,
            scoretype,
            totalpointvalue,

            'assignment_detail' as row_type,

        from assignment_detail
    ),

    student_flags_aggregate as (
        select
            _dbt_source_project,
            sectionid,
            `quarter`,

            countif(qt_percent_grade_greater_100) > 0 as has_grade_above_100,
            countif(qt_grade_70_comment_missing) > 0 as has_grade_below_70_no_comment,

        from {{ ref("int_extracts__gradebook_audit_student_flags") }}
        group by _dbt_source_project, sectionid, `quarter`
    ),

    with_section_flags as (
        select
            c.*,

            if(
                sf._dbt_source_project is not null, sf.has_grade_above_100, false
            ) as has_grade_above_100,

            if(
                sf._dbt_source_project is not null,
                sf.has_grade_below_70_no_comment,
                false
            ) as has_grade_below_70_no_comment,

        from combined as c
        left join
            student_flags_aggregate as sf
            on c._dbt_source_project = sf._dbt_source_project
            and c.sectionid = sf.sectionid
            and c.`quarter` = sf.`quarter`
    ),

    health_calc as (
        select
            _dbt_source_project,
            academic_year,
            schoolid,
            teacher_number,
            `quarter`,

            not logical_or(
                not_enough_assignments
                or has_grade_above_100
                or has_grade_below_70_no_comment
            ) as is_healthy_gradebook_all_flags,

            not logical_or(
                not_enough_assignments or has_grade_above_100
            ) as is_healthy_gradebook_excl_comments,

        from with_section_flags
        group by _dbt_source_project, academic_year, schoolid, teacher_number, `quarter`
    )

select
    w._dbt_source_project,
    w.academic_year,
    w.academic_year_display,
    w.region_school_level,
    w.region,
    w.school_level,
    w.schoolid,
    w.school,

    w.course_number,
    w.course_name,
    w.credit_type,
    w.exclude_from_gpa,
    w.sections_dcid,
    w.sectionid,
    w.section_number,
    w.external_expression,
    w.section_or_period,
    w.teacher_number,
    w.teacher_name,
    w.teacher_employee_number,
    w.school_leader,
    w.manager_employee_number,
    w.manager_name,
    w.hos,

    w.teacher_tableau_username,
    w.manager_tableau_username,
    w.school_leader_tableau_username,

    w.`quarter`,
    w.semester,
    w.quarter_start_date,
    w.quarter_end_date,
    w.is_current_quarter,

    w.row_type,

    w.assignment_category_code,
    w.assignment_category_name,
    w.assignment_category_term,
    w.expectation,
    w.assignments_entered_count,
    w.not_enough_assignments,

    w.assignmentid,
    w.assignment_name,
    w.duedate,
    w.scoretype,
    w.totalpointvalue,

    w.has_grade_above_100,
    w.has_grade_below_70_no_comment,

    h.is_healthy_gradebook_all_flags,
    h.is_healthy_gradebook_excl_comments,

from with_section_flags as w
inner join
    health_calc as h
    on w._dbt_source_project = h._dbt_source_project
    and w.academic_year = h.academic_year
    and w.schoolid = h.schoolid
    and w.teacher_number = h.teacher_number
    and w.`quarter` = h.`quarter`
