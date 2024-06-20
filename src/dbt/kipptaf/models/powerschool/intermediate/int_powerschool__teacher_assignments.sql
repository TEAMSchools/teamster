with
    sections as (
        select
            sec._dbt_source_relation,
            sec.sections_dcid,
            sec.sections_id as section_id,
            sec.sections_schoolid as schoolid,
            sec.sections_course_number as course_number,
            sec.teachernumber as teacher_number,
            sec.teacher_lastfirst,
            sec.terms_yearid as yearid,

            sec.terms_yearid + 1990 as academic_year,
            initcap(regexp_extract(sec._dbt_source_relation, r'kipp(\w+)_')) as region,

            case
                sch.high_grade when 4 then 'ES' when 8 then 'MS' when 12 then 'HS'
            end as grade_band,

            if(
                sch.high_grade in (4, 8),
                s.sections_section_number,
                s.sections_external_expression
            ) as section_or_period,
        from {{ ref("base_powerschool__sections") }} as sec
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on sec.sections_schoolid = sch.school_number
            and {{ union_dataset_join_clause(left_alias="sec", right_alias="sch") }}
        where
            sec.sections_course_number not in (
                'HR',
                'LOG100',
                'LOG1010',
                'LOG11',
                'LOG12',
                'LOG20',
                'LOG22999XL',
                'LOG300',
                'LOG9',
                'SEM22106G1',
                'SEM22106S1'
            )
            and sec.terms_firstday >= date({{ var("current_academic_year") }}, 7, 1)
    ),

    valid_sections as (
        select
            _dbt_source_relation,
            sections_dcid,
            section_id,
            schoolid,
            section_or_period,
            course_number,
            teacher_number,
            teacher_lastfirst,
            yearid,
            academic_year,
            region,
            grade_band,
        from sections
        where region = 'Miami'

        union all

        select
            _dbt_source_relation,
            sections_dcid,
            section_id,
            schoolid,
            section_or_period,
            course_number,
            teacher_number,
            teacher_lastfirst,
            yearid,
            academic_year,
            region,
            grade_band,
        from sections
        where grade_band in ('MS', 'HS') and region != 'Miami'
    ),

    expectations as (
        select
            vs._dbt_source_relation,
            vs.sections_dcid,
            vs.section_id,
            vs.schoolid,
            vs.section_or_period,
            vs.course_number,
            vs.teacher_number,
            vs.teacher_lastfirst,
            vs.yearid,
            vs.academic_year,
            vs.region,
            vs.grade_band,

            c.semester,
            c.quarter,
            c.week_number_quarter,
            c.week_number_academic_year,
            c.week_start_date,
            c.week_end_date,
            c.school_week_start_date,
            c.school_week_end_date,
            c.school_week_start_date_lead,

            ge.assignment_category_code,
            ge.assignment_category_term,
            ge.expectation,

            case
                ge.assignment_category_code,
                when 'W'
                then 'Work Habits'
                when 'F'
                then 'Formative Mastery'
                when 'S'
                then 'Summative Mastery'
            end as assignment_category_name,
        from valid_sections as vs
        inner join
            {{ ref("int_powerschool__calendar_week") }} as c
            on vs.cc_schoolid = c.schoolid
            and vs.cc_yearid = c.yearid
            and c.week_end_date between ce.cc_dateenrolled and ce.cc_dateleft
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="c") }}
        inner join
            {{ ref("stg_reporting__gradebook_expectations") }} as ge
            on c.academic_year = ge.academic_year
            and c.region = ge.region
            and c.quarter = ge.quarter
            and c.week_number_quarter = ge.week_number
    ),

    assign_3 as (
        select
            t._dbt_source_relation,
            t.yearid,
            t.academic_year,
            t.region,
            t.schoolid,
            t.school_level,
            t.teacher_number,
            t.teacher_name,
            t.course_number,
            t.section_or_period,
            t.sectionid,
            t.sections_dcid,
            t.teacher_semester_code,
            t.teacher_quarter,
            t.audit_yr_week_number,
            t.audit_qt_week_number,
            t.audit_start_date,
            t.audit_end_date,
            t.audit_due_date,
            t.expected_teacher_assign_category_code,
            t.expected_teacher_assign_category_name,
            t.audit_category_exp_audit_week_ytd,

            a.assign_id as teacher_assign_id,
            a.assign_name as teacher_assign_name,
            a.assign_score_type as teacher_assign_score_type,
            a.assign_max_score as teacher_assign_max_score,
            a.assign_due_date as teacher_assign_due_date,

            if(a.assign_id is null, 0, 1) as teacher_assign_count,

            if(
                sum(if(a.assign_id is null, 0, 1)) over (
                    partition by
                        t.schoolid,
                        t.teacher_name,
                        t.course_number,
                        t.section_or_period,
                        t.teacher_quarter,
                        t.expected_teacher_assign_category_code
                    order by t.teacher_quarter, t.audit_qt_week_number
                )
                >= t.audit_category_exp_audit_week_ytd,
                0,
                1
            ) as teacher_category_assign_count_expected_not_met,

            sum(if(a.assign_id is null, 0, 1)) over (
                partition by
                    t.schoolid,
                    t.teacher_name,
                    t.course_number,
                    t.section_or_period,
                    t.teacher_quarter,
                    t.expected_teacher_assign_category_code
                order by t.teacher_quarter, t.audit_qt_week_number
            ) as teacher_running_total_assign_by_cat,
        from expectations as t
        left join
            {{ ref("int_powerschool__student_assignments") }} as a
            on t.course_number = a.course_number
            and t.sections_dcid = a.sections_dcid
            and t.teacher_name = a.teacher_name
            and t.teacher_quarter = a.assign_quarter
            and t.audit_qt_week_number = a.audit_qt_week_number
            and t.expected_teacher_assign_category_name = a.assign_category
            and {{ union_dataset_join_clause(left_alias="t", right_alias="a") }}
    ),

    assign_4 as (
        select
            t._dbt_source_relation,
            t.yearid,
            t.academic_year,
            t.region,
            t.schoolid,
            t.school_level,
            t.teacher_number,
            t.teacher_name,
            t.course_number,
            t.section_or_period,
            t.sectionid,
            t.sections_dcid,
            t.teacher_semester_code,
            t.teacher_quarter,
            t.audit_yr_week_number,
            t.audit_qt_week_number,
            t.audit_start_date,
            t.audit_end_date,
            t.audit_due_date,
            t.expected_teacher_assign_category_code,
            t.expected_teacher_assign_category_name,
            t.audit_category_exp_audit_week_ytd,
            t.teacher_assign_id,
            t.teacher_assign_name,
            t.teacher_assign_score_type,
            t.teacher_assign_max_score,
            t.teacher_assign_due_date,
            t.teacher_assign_count,
            t.teacher_running_total_assign_by_cat,
            t.teacher_category_assign_count_expected_not_met,

            avg(
                if(
                    asg.assign_expected_with_score = 1,
                    asg.assign_final_score_percent,
                    null
                )
            ) over (
                partition by
                    t.schoolid,
                    t.teacher_quarter,
                    t.teacher_name,
                    t.course_number,
                    t.section_or_period,
                    t.teacher_assign_id
            ) as teacher_avg_score_for_assign_per_class_section_and_assign_id,

            sum(asg.assign_expected_with_score) over (
                partition by
                    t.schoolid,
                    t.teacher_name,
                    t.teacher_quarter,
                    t.audit_qt_week_number,
                    asg.assign_category_code
            ) as
            total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,

            sum(asg.assign_expected_to_be_scored) over (
                partition by
                    t.schoolid,
                    t.teacher_name,
                    t.teacher_quarter,
                    t.audit_qt_week_number,
                    asg.assign_category_code
            ) as total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,

            sum(asg.assign_expected_with_score) over (
                partition by
                    t.schoolid,
                    t.teacher_quarter,
                    t.audit_qt_week_number,
                    t.course_number,
                    t.section_or_period,
                    asg.assign_category_code
            ) as total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,

            sum(asg.assign_expected_to_be_scored) over (
                partition by
                    t.schoolid,
                    t.teacher_quarter,
                    t.audit_qt_week_number,
                    t.course_number,
                    t.section_or_period,
                    asg.assign_category_code
            ) as total_expected_graded_assignments_by_course_cat_qt_audit_week,

            sum(asg.assign_expected_with_score) over (
                partition by
                    t.schoolid,
                    t.course_number,
                    t.sectionid,
                    t.teacher_quarter,
                    t.audit_qt_week_number,
                    asg.assign_category,
                    asg.assign_id
            ) as
            total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,

            sum(asg.assign_expected_to_be_scored) over (
                partition by
                    t.schoolid,
                    t.course_number,
                    t.sectionid,
                    t.teacher_quarter,
                    t.audit_qt_week_number,
                    asg.assign_category,
                    asg.assign_id
            ) as total_expected_graded_assignments_by_course_assign_id_qt_audit_week,

            -- flags
            if(
                sum(asg.assign_is_missing) over (
                    partition by
                        t.schoolid,
                        t.teacher_quarter,
                        t.teacher_name,
                        t.course_number,
                        t.section_or_period
                )
                = 0,
                1,
                0
            ) as qt_teacher_no_missing_assignments,

            if(
                asg.assign_category_code = 'S'
                and asg.assign_expected_to_be_scored = 1
                and (
                    sum(distinct t.teacher_assign_max_score) over (
                        partition by
                            t.schoolid,
                            t.teacher_quarter,
                            t.teacher_name,
                            t.course_number,
                            t.section_or_period
                    )
                    < 200
                ),
                1,
                0
            ) as qt_teacher_s_total_less_200,

            if(
                asg.assign_category_code = 'S'
                and asg.assign_expected_to_be_scored = 1
                and (
                    sum(distinct t.teacher_assign_max_score) over (
                        partition by
                            t.schoolid,
                            t.teacher_quarter,
                            t.teacher_name,
                            t.course_number,
                            t.section_or_period
                    )
                    > 200
                ),
                1,
                0
            ) as qt_teacher_s_total_greater_200,

        from assign_3 as t
        left join
            {{ ref("int_powerschool__student_assignments") }} as asg
            on t.academic_year = asg.academic_year
            and t.schoolid = asg.schoolid
            and t.course_number = asg.course_number
            and t.sections_dcid = asg.sections_dcid
            and t.expected_teacher_assign_category_code = asg.assign_category_code
            and t.teacher_assign_id = asg.assign_id
            and {{ union_dataset_join_clause(left_alias="t", right_alias="asg") }}
    )

select
    _dbt_source_relation,
    yearid,
    academic_year,
    region,
    schoolid,
    school_level,
    teacher_number,
    teacher_name,
    course_number,
    section_or_period,
    sectionid,
    sections_dcid,
    teacher_semester_code,
    teacher_quarter,
    audit_yr_week_number,
    audit_qt_week_number,
    audit_start_date,
    audit_end_date,
    audit_due_date,
    expected_teacher_assign_category_code,
    expected_teacher_assign_category_name,
    audit_category_exp_audit_week_ytd,
    teacher_assign_id,
    teacher_assign_name,
    teacher_assign_score_type,
    teacher_assign_max_score,
    teacher_assign_due_date,
    teacher_assign_count,
    teacher_running_total_assign_by_cat,
    teacher_avg_score_for_assign_per_class_section_and_assign_id,
    total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
    total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,
    total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
    total_expected_graded_assignments_by_course_cat_qt_audit_week,
    total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,
    total_expected_graded_assignments_by_course_assign_id_qt_audit_week,

    qt_teacher_no_missing_assignments,
    qt_teacher_s_total_less_200,
    qt_teacher_s_total_greater_200,

    if(
        expected_teacher_assign_category_code = 'W'
        and teacher_category_assign_count_expected_not_met = 1,
        1,
        0
    ) as w_expected_assign_count_not_met,

    if(
        expected_teacher_assign_category_code = 'F'
        and teacher_category_assign_count_expected_not_met = 1,
        1,
        0
    ) as f_expected_assign_count_not_met,

    if(
        expected_teacher_assign_category_code = 'S'
        and teacher_category_assign_count_expected_not_met = 1,
        1,
        0
    ) as s_expected_assign_count_not_met,

    if(
        expected_teacher_assign_category_code = 'W' and teacher_assign_max_score != 10,
        1,
        0
    ) as w_assign_max_score_not_10,

    if(
        expected_teacher_assign_category_code = 'F' and teacher_assign_max_score != 10,
        1,
        0
    ) as f_assign_max_score_not_10,

    if(
        region = 'FL'
        and expected_teacher_assign_category_code = 'S'
        and teacher_assign_max_score > 100,
        1,
        0
    ) as s_max_score_greater_100,

    round(
        safe_divide(
            total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
            total_expected_graded_assignments_by_cat_qt_audit_week_all_courses
        ),
        2
    ) as percent_graded_completion_by_cat_qt_audit_week_all_courses,

    round(
        safe_divide(
            total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
            total_expected_graded_assignments_by_course_cat_qt_audit_week
        ),
        2
    ) as percent_graded_completion_by_cat_qt_audit_week,

    round(
        safe_divide(
            total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,
            total_expected_graded_assignments_by_course_assign_id_qt_audit_week
        ),
        2
    ) as percent_graded_completion_by_assign_id_qt_audit_week,

from assign_4
