with
    marking_periods as (
        select
            marking_period_id,
            syear,
            school_id,
            title,
            short_name,
            type,
            start_date,
            end_date,

            if(type = 'year', 0, marking_period_id) as schedule_marking_period_id,
        from {{ ref("stg_focus__marking_periods") }}
    ),

    enrollment_end as (
        select
            student_id,
            school_id,
            syear,

            if(
                countif(end_date is null) > 0, null, max(end_date)
            ) as enrollment_end_date,
        from {{ ref("stg_focus__student_enrollment") }}
        group by student_id, school_id, syear
    ),

    enrollment_gaps as (
        select
            student_id,
            school_id,
            syear,
            end_date,

            lead(start_date) over (
                partition by student_id, school_id, syear order by start_date
            ) as next_start_date,
        from {{ ref("stg_focus__student_enrollment") }}
    ),

    withdrawal_closes as (
        -- grain projection, not dup-masking: one row per seat closed in a gap
        select distinct s.id as student_schedule_id,
        from {{ ref("stg_focus__schedule") }} as s
        inner join
            enrollment_gaps as g
            on s.student_id = g.student_id
            and s.school_id = g.school_id
            and s.syear = g.syear
            and g.end_date <= s.end_date
            and (g.next_start_date is null or s.end_date < g.next_start_date)
    ),

    schedule as (
        select
            s.id as student_schedule_id,
            s.syear as academic_year,
            s.school_id as schoolid,
            s.student_id,
            s.course_id,
            s.course_period_id,
            s.mp,
            s.course_weight,
            s.days,
            s.rotation_days,
            s.start_date,
            s.end_date,
            s.fefp_number,
            s.dual_enrollment_indicator,
            s.class_minutes_weekly,
            s.reading_intervention_component,
            s.basic_skills_exam,
            s.location_of_student,
            s.eoc_exam_term,
            s.exempt_from_total_clock_hours,
            s.exclude_from_fte,
            s.pmrn,

            cp.title as course_period_title,
            cp.short_name as course_period_short_name,
            cp.custom_title as course_period_custom_title,
            cp.teacher_id,
            cp.room,
            cp.period_id,
            cp.calendar_id,
            cp.team_id,
            cp.grade_scale_id,
            cp.credits,
            cp.does_attendance,
            cp.does_grades,
            cp.does_gpa,

            c.title as course_title,
            c.short_name as course_short_name,
            c.subject_id,
            c.grad_subject_id,
            c.grade_level as course_grade_level,
            c.credit_hours,
            c.course_hours,
            c.homeroom,

            -- aliased mkp, not mp: schedule has its own mp column (the FY/SEM/QTR code)
            mkp.marking_period_id,
            mkp.title as marking_period_title,
            mkp.short_name as marking_period_short_name,
            mkp.type as marking_period_type,
            mkp.start_date as marking_period_start_date,
            mkp.end_date as marking_period_end_date,

            (
                select min(d),
                from unnest([s.end_date, mkp.end_date, ee.enrollment_end_date]) as d
            ) as effective_end_date,

            -- coalesce is required: end_date is null on open seats
            coalesce(s.end_date < mkp.end_date, false)
            and wc.student_schedule_id is null as is_dropped,
        from {{ ref("stg_focus__schedule") }} as s
        inner join
            {{ ref("stg_focus__course_periods") }} as cp
            on s.course_period_id = cp.course_period_id
        inner join {{ ref("stg_focus__courses") }} as c on s.course_id = c.course_id
        left join
            marking_periods as mkp
            on s.syear = mkp.syear
            and s.school_id = mkp.school_id
            and s.marking_period_id = mkp.schedule_marking_period_id
        left join
            enrollment_end as ee
            on s.student_id = ee.student_id
            and s.school_id = ee.school_id
            and s.syear = ee.syear
        left join withdrawal_closes as wc on s.id = wc.student_schedule_id
        -- drop seats Focus scheduled after the student left, before the stint pick
        where ee.enrollment_end_date is null or s.start_date <= ee.enrollment_end_date
    )

    -- one stint per course period; the pick order is in the model description
    {{
        dbt_utils.deduplicate(
            relation="schedule",
            partition_by="student_id, course_period_id",
            order_by="(end_date is not null) asc, (mp is distinct from 'FY') asc, student_schedule_id desc",
        )
    }}
