with
    nj_scores as (
        select
            student_test_uuid,
            academic_year,
            test_date,
            grade_level_when_assessed,
            discipline,
            test_code,
            student_growth_percentile,
            is_proficient,
            aligned_aggregate_ethnicity,
            is_student_with_disabilities,
            aligned_ml_status,
            is_economically_disadvantaged,

            {{ student_key("student_number") }} as student_key,
        from {{ ref("int_assessments__state_nj_scores") }}
        where student_growth_percentile is not null
    ),

    scores as (
        select
            ns.student_test_uuid,
            ns.student_key,
            ns.academic_year,
            ns.test_date,
            ns.grade_level_when_assessed as grade_level_tested,
            ns.discipline as subject,
            ns.test_code,
            ns.student_growth_percentile,
            ns.is_proficient,
            ns.is_student_with_disabilities,
            ns.is_economically_disadvantaged,

            l.location_key,
            l.abbreviation as school,
            l.grade_band,

            r.name as region,

            if(
                ns.aligned_aggregate_ethnicity = 'Other',
                'Two or more races',
                ns.aligned_aggregate_ethnicity
            ) as race_ethnicity_group,

            ns.aligned_ml_status = 'ML' as is_multilingual_learner,

            -- NJDOE's growth bands: below 35, 35 through 65, above 65
            case
                when ns.student_growth_percentile < 35
                then 'Low'
                when ns.student_growth_percentile > 65
                then 'High'
                else 'Typical'
            end as growth_level,
        from nj_scores as ns
        left join
            {{ ref("dim_student_enrollments") }} as e
            on ns.student_key = e.student_key
            and ns.academic_year = e.academic_year
            and ns.test_date >= e.entry_date_key
            and ns.test_date < e.exit_date_key
        left join {{ ref("dim_locations") }} as l on e.location_key = l.location_key
        left join {{ ref("dim_regions") }} as r on l.region_key = r.region_key
    ),

    window_days as (
        select
            s.student_test_uuid,

            sc.date_key,

            count(sc.date_key) over (
                partition by s.student_test_uuid
            ) as window_day_count,
        from scores as s
        inner join
            {{ ref("dim_school_calendars") }} as sc
            on s.location_key = sc.location_key
            and s.test_date > sc.date_key
            and sc.is_in_session
        inner join
            {{ ref("dim_dates") }} as d
            on sc.date_key = d.date_key
            and s.academic_year = d.academic_year
    ),

    sections as (
        select
            s.student_test_uuid,

            -- sections the student left stay in; their dates bound the days
            sse.course_section_key,
            sse.entry_date,
            sse.exit_date,
        from scores as s
        inner join
            {{ ref("dim_student_enrollments") }} as e
            on s.student_key = e.student_key
            and s.academic_year = e.academic_year
        inner join
            {{ ref("dim_student_section_enrollments") }} as sse
            on e.student_enrollment_key = sse.student_enrollment_key
            and not sse.is_homeroom
        inner join
            {{ ref("dim_course_sections") }} as cs
            on sse.course_section_key = cs.course_section_key
            and s.location_key = cs.location_key
        inner join
            {{ ref("dim_courses") }} as c
            on cs.course_key = c.course_key
            and s.subject = c.academic_subject
    ),

    assignments as (
        select
            course_section_key,
            staff_key,

            -- a missing start or end date leaves the assignment open on that side
            coalesce(effective_start_date, '0001-01-01') as effective_start_date,
            coalesce(effective_end_date, '9999-12-31') as effective_end_date,

            `role` = 'Lead Teacher' as is_lead,
        from {{ ref("bridge_course_section_teachers") }}
        -- the 2 roles the state credits; Gradebook Access and the rest do not
        where `role` in ('Lead Teacher', 'Co-teacher')
    ),

    teacher_section_share as (
        select
            w.student_test_uuid,
            w.window_day_count,

            a.course_section_key,
            a.staff_key,

            logical_or(a.is_lead) as is_lead,

            safe_divide(
                count(distinct w.date_key), w.window_day_count
            ) as teacher_share,
        from window_days as w
        inner join sections as sec on w.student_test_uuid = sec.student_test_uuid
        inner join
            assignments as a
            on sec.course_section_key = a.course_section_key
            and w.date_key >= a.effective_start_date
            and w.date_key <= a.effective_end_date
        group by
            w.student_test_uuid, w.window_day_count, a.course_section_key, a.staff_key
    ),

    student_teacher_days as (
        select
            tss.student_test_uuid,
            tss.staff_key,
            tss.window_day_count,

            count(distinct w.date_key) as student_day_count,
            max(tss.teacher_share) as teacher_share,
            logical_or(tss.is_lead) as is_lead,

            safe_divide(
                count(distinct w.date_key), tss.window_day_count
            ) as student_share,
        from teacher_section_share as tss
        inner join
            sections as sec
            on tss.student_test_uuid = sec.student_test_uuid
            and tss.course_section_key = sec.course_section_key
        inner join
            window_days as w
            on sec.student_test_uuid = w.student_test_uuid
            and sec.entry_date <= w.date_key
            and sec.exit_date > w.date_key
        -- the state's teacher rule: assigned for at least 60% of the window
        where tss.teacher_share >= 0.60
        group by tss.student_test_uuid, tss.staff_key, tss.window_day_count
    ),

    matches as (
        select
            std.student_test_uuid,
            std.staff_key,
            std.window_day_count,
            std.student_day_count,
            std.student_share,
            std.teacher_share,

            s.student_key,
            s.academic_year,
            s.location_key,
            s.subject,

            if(std.is_lead, 'Lead Teacher', 'Co-teacher') as teacher_role,
        from student_teacher_days as std
        inner join scores as s on std.student_test_uuid = s.student_test_uuid
        -- the state's student rule: enrolled for at least 70% of the window
        where std.student_share >= 0.70
    ),

    teacher_shared_students as (
        select
            m.staff_key,
            m.academic_year,
            m.location_key,
            m.subject,

            count(distinct m.student_key) as teacher_shared_student_count,
            count(distinct o.staff_key) as teacher_other_teacher_count,
        from matches as m
        inner join
            matches as o
            on m.student_test_uuid = o.student_test_uuid
            and m.staff_key != o.staff_key
        group by m.staff_key, m.academic_year, m.location_key, m.subject
    ),

    teacher_lead_subjects as (
        select
            staff_key,
            academic_year,
            location_key,

            -- at least 10 lead students per subject, so a stray row cannot set it
            count(distinct if(subject = 'ELA', student_key, null)) >= 10
            and count(distinct if(subject = 'Math', student_key, null))
            >= 10 as is_lead_in_both_subjects,
        from matches
        where teacher_role = 'Lead Teacher'
        group by staff_key, academic_year, location_key
    )

select
    m.student_test_uuid,
    m.staff_key,
    m.teacher_role,
    m.window_day_count,
    m.student_day_count,
    m.student_share,
    m.teacher_share,

    s.student_key,
    s.academic_year,
    s.test_date,
    s.region,
    s.location_key,
    s.school,
    s.grade_band,
    s.grade_level_tested,
    s.subject,
    s.test_code,
    s.student_growth_percentile,
    s.growth_level,
    s.is_proficient,
    s.race_ethnicity_group,
    s.is_student_with_disabilities,
    s.is_multilingual_learner,
    s.is_economically_disadvantaged,

    st.full_name as teacher_name,

    coalesce(tsh.teacher_shared_student_count, 0) as teacher_shared_student_count,
    coalesce(tsh.teacher_other_teacher_count, 0) as teacher_other_teacher_count,
    coalesce(tls.is_lead_in_both_subjects, false) as is_lead_in_both_subjects,
from matches as m
inner join scores as s on m.student_test_uuid = s.student_test_uuid
left join {{ ref("dim_staff") }} as st on m.staff_key = st.staff_key
left join
    teacher_shared_students as tsh
    on m.staff_key = tsh.staff_key
    and m.academic_year = tsh.academic_year
    and m.location_key = tsh.location_key
    and m.subject = tsh.subject
left join
    teacher_lead_subjects as tls
    on m.staff_key = tls.staff_key
    and m.academic_year = tls.academic_year
    and m.location_key = tls.location_key
