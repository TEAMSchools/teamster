with
    student_schedule as (
        select
            id,
            syear,
            school_id,
            student_id,
            course_id,
            course_period_id,
            mp,
            course_weight,
            days,
            rotation_days,
            start_date,
            end_date,
            fefp_number,
            dual_enrollment_indicator,
            class_minutes_weekly,
            reading_intervention_component,
            basic_skills_exam,
            location_of_student,
            eoc_exam_term,
            exempt_from_total_clock_hours,
            exclude_from_fte,
            pmrn,

            -- Focus stores 0, not null, for a full-year schedule (mp = 'FY'), so
            -- normalize it before joining or those rows read as unresolvable
            -- marking-period ids
            nullif(marking_period_id, 0) as marking_period_id,
        from {{ ref("stg_focus__schedule") }}
    )

select
    s.id as student_schedule_id,
    s.syear as academic_year,
    s.school_id as schoolid,
    s.student_id,
    s.course_id,
    s.course_period_id,
    s.marking_period_id,
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

    mp.title as marking_period_title,
    mp.short_name as marking_period_short_name,
    mp.type as marking_period_type,
    mp.start_date as marking_period_start_date,
    mp.end_date as marking_period_end_date,

from student_schedule as s
inner join
    {{ ref("stg_focus__course_periods") }} as cp
    on s.course_period_id = cp.course_period_id
inner join {{ ref("stg_focus__courses") }} as c on s.course_id = c.course_id
left join
    {{ ref("stg_focus__marking_periods") }} as mp
    on s.marking_period_id = mp.marking_period_id
