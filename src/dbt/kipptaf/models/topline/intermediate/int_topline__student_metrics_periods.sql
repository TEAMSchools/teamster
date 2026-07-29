with
    metric_union as (
        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'Attendance and Enrollment' as layer,
            'ADA' as indicator,
            cast(null as string) as discipline,

            attendance_value_sum as numerator,
            membership_value_sum as denominator,
            ada_period as metric_value,
        from {{ ref("int_topline__attendance_period") }}

        union all

        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'Attendance and Enrollment' as layer,
            'Truancy' as indicator,
            cast(null as string) as discipline,

            null as numerator,
            null as denominator,

            is_truant_period_int as metric_value,
        from {{ ref("int_topline__attendance_period") }}

        union all

        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'Attendance and Enrollment' as layer,
            'Chronic Absenteeism' as indicator,
            cast(null as string) as discipline,

            null as numerator,
            null as denominator,

            is_chronically_absent_period_int as metric_value,
        from {{ ref("int_topline__attendance_period") }}

        union all

        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'Attendance and Enrollment' as layer,
            'Successful Contacts' as indicator,
            cast(null as string) as discipline,

            successful_comms_sum as numerator,
            required_comms_count as denominator,

            safe_divide(successful_comms_sum, required_comms_count) as metric_value,
        from {{ ref("int_topline__attendance_contacts_period") }}

        union all

        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'Student and Family Experience' as layer,
            'Suspensions' as indicator,
            cast(null as string) as discipline,

            null as numerator,
            null as denominator,

            is_suspended_period_int as metric_value,
        from {{ ref("int_topline__suspension_period") }}

        union all

        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'K-8 Reading and Math' as layer,
            'i-Ready Lessons Passed' as indicator,
            discipline,

            null as numerator,
            null as denominator,

            meets_lessons_passed_period_int as metric_value,
        from {{ ref("int_topline__iready_lessons_period") }}

        union all

        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'K-8 Reading and Math' as layer,
            'i-Ready Time on Task' as indicator,
            discipline,

            null as numerator,
            null as denominator,

            time_on_task_min_week_avg as metric_value,
        from {{ ref("int_topline__iready_lessons_period") }}
    ),

    /* all calendar weeks per student x school-year (not just enrolled weeks) —
       matches the weekly path's spine semantics so window-edge activity keeps
       its attribution */
    spine_weeks as (
        select
            student_number,
            academic_year,
            schoolid,
            region,
            school,
            grade_level,
            week_start_monday,
        from {{ ref("int_extracts__student_enrollments_weeks") }}
        where
            academic_year >= {{ var("current_academic_year") - 1 }}
            and region != 'Paterson'
    ),

    attrs_ranked as (
        select
            mu.*,

            ew.region,
            ew.school,
            ew.grade_level,

            max(ew.week_start_monday) over (
                partition by
                    mu.student_number,
                    mu.academic_year,
                    mu.schoolid,
                    mu.layer,
                    mu.indicator,
                    mu.discipline,
                    mu.period_type,
                    mu.period_label
            ) as max_week_in_period,

            ew.week_start_monday as attr_week,
        from metric_union as mu
        inner join
            spine_weeks as ew
            on mu.student_number = ew.student_number
            and mu.academic_year = ew.academic_year
            and mu.schoolid = ew.schoolid
            and ew.week_start_monday between mu.period_start and mu.period_end
    )

select
    student_number,
    academic_year,
    region,
    schoolid,
    school,
    grade_level,
    layer,
    indicator,
    discipline,
    period_type,
    period_label,
    numerator,
    denominator,
    metric_value,

    period_start as term,
    period_end as term_end,
from attrs_ranked
where attr_week = max_week_in_period
