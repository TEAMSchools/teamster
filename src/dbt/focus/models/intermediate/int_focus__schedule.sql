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
    )

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
