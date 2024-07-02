with
    iready_weekly as (
        select
            student_id as student_number,
            academic_year_int as academic_year,
            last_week_start_date,
            last_week_end_date,
            coalesce(n_lessons_passed_reading, 0) as n_lessons_passed_reading,
            coalesce(n_lessons_passed_math, 0) as n_lessons_passed_math,
            coalesce(pct_lessons_passed_reading, 0) as pct_lessons_passed_reading,
            coalesce(pct_lessons_passed_math, 0) as pct_lessons_passed_math,
            coalesce(time_on_task_reading, 0) as time_on_task_reading,
            coalesce(time_on_task_math, 0) as time_on_task_math,
            row_number() over (
                partition by student_id, last_week_start_date
                order by last_week_start_date asc
            ) as rn_iready_week,
        from
            (
                select
                    student_id,
                    academic_year_int,
                    lower(subject) as subject,
                    last_week_start_date,
                    last_week_end_date,
                    last_week_lessons_passed,
                    last_week_percent_lessons_passed,
                    last_week_time_on_task_min,
                from {{ ref("snapshot_iready__instructional_usage_data") }}
            ) pivot (
                max(last_week_lessons_passed) as n_lessons_passed,
                max(last_week_percent_lessons_passed) as pct_lessons_passed,
                max(last_week_time_on_task_min) as time_on_task for subject
                in ('reading', 'math')
            )
    )

select
    w.week_start_monday,
    w.week_end_sunday,
    w.days_in_session,
    w.term,

    co.student_number,
    co.lastfirst as student_name,
    co.academic_year,
    co.schoolid,
    co.school_abbreviation as school,
    co.region,
    co.grade_level,
    co.enroll_status,
    co.cohort,
    co.school_level,
    co.gender,
    co.ethnicity,

    r.assessment_id,
    r.title,
    r.scope,
    r.subject_area,
    r.administered_at,
    r.date_taken,
    r.module_type,
    r.module_number,
    r.response_type,
    r.response_type_code,
    r.response_type_description,
    r.response_type_root_description,
    r.percent_correct,
    r.is_mastery,
    r.performance_band_label_number,
    r.performance_band_label,
    r.is_replacement,

    qbl.qbl,

    hr.sections_section_number as homeroom_section,
    hr.teachernumber as homeroom_teachernumber,
    hr.teacher_lastfirst as homeroom_teacher_name,

    cc.sections_section_number as course_section,
    cc.courses_course_name as course_name,
    cc.courses_course_number as course_number,
    cc.courses_credittype as course_credittype,
    cc.teachernumber as course_teachernumber,
    cc.teacher_lastfirst as course_teacher_name,

    iw.n_lessons_passed_reading,
    iw.n_lessons_passed_math,
    iw.pct_lessons_passed_reading,
    iw.pct_lessons_passed_math,
    iw.time_on_task_reading,
    iw.time_on_task_math,

    if(r.is_mastery, 1, 0) as is_mastery_int,
    concat(
        'https://kippteamschools.illuminateed.com/live/?assessment_id=',
        r.assessment_id,
        '&page=Assessments_Overview_Controller'
    ) as illuminate_overview_link,
    concat(
        'https://kippteamschools.illuminateed.com/live/?page=PrebuiltReport_AssessmentResponseDistributionController&assessment_id=',
        r.assessment_id,
        '&code_prebuilt_id=370&action=showReport&create_student_group=t&fw_form_form_test=1&site_id=',
        co.schoolid,
        '&date=logged_in_date&group_by=overall&response_count_format=number&guid=21fa0ddf-1f3b-4918-80d9-f2088bcc7f48&reference_id=PR&state_id=31'
    ) as illuminate_response_freq,

    if(qbl.qbl is not null, true, false) as is_qbl,

    if(co.lep_status, 'ML', 'Not ML') as ml_status,
    if(co.is_504, 'Has 504', 'No 504') as status_504,
    if(
        co.is_self_contained, 'Self-contained', 'Not self-contained'
    ) as self_contained_status,
    if(co.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("int_reporting__week_scaffold") }} as w
    on co.academic_year = w.academic_year
    and co.schoolid = w.schoolid
    and w.week_end_sunday between co.entrydate and co.exitdate
left join
    {{ ref("int_assessments__response_rollup") }} as r
    on co.student_number = r.powerschool_student_number
    and co.academic_year = r.academic_year
    and r.administered_at between w.week_start_monday and w.week_end_sunday
    and r.module_type is not null
left join
    {{ ref("stg_assessments__qbls_power_standards") }} as qbl
    on co.academic_year = qbl.academic_year
    and co.region = qbl.region
    and co.grade_level = qbl.grade_level
    and r.response_type_code = qbl.standard_code
    and r.subject_area = qbl.illuminate_subject_area
    and qbl.qbl is not null
left join
    {{ ref("base_powerschool__course_enrollments") }} as cc
    on co.studentid = cc.cc_studentid
    and co.yearid = cc.cc_yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="cc") }}
    and r.subject_area = cc.illuminate_subject_area
    and not cc.is_dropped_section
    and cc.rn_student_year_illuminate_subject_desc = 1
left join
    {{ ref("base_powerschool__course_enrollments") }} as hr
    on co.student_number = hr.cc_studentid
    and co.yearid = hr.cc_yearid
    and co.schoolid = hr.cc_schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="hr") }}
    and hr.cc_course_number = 'HR'
    and not hr.is_dropped_section
    and hr.rn_course_number_year = 1
left join
    iready_weekly as iw
    on co.student_number = iw.student_number
    and co.academic_year = iw.academic_year
    and w.week_start_monday = iw.last_week_start_date
    and w.week_end_sunday = iw.last_week_end_date
    and iw.rn_iready_week = 1
-- left join {{ ref('snapshot_iready__instructional_usage_data') }} as iue
-- co.student_number = iu.student_id
-- and co.academic_year = iu.academic_year_int
-- and w.week_start_monday = iu.last_week_start_date
-- left join
-- {{ ref("stg_reporting__terms") }} as t
-- on co.schoolid = t.school_id
-- and co.academic_year = t.academic_year
-- and r.administered_at between t.start_date and t.end_date
-- and t.type = 'RT'
where
    co.rn_year = 1
    and co.grade_level between 0 and 8
    and co.enroll_status = 0
    and co.academic_year >= {{ var("current_academic_year") }} - 1
