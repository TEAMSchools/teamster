with
    iready_usage as (
        select
            student_id,
            academic_year_int,
            last_week_start_date,
            last_week_end_date,
            last_week_lessons_passed,
            last_week_percent_lessons_passed,
            last_week_time_on_task_min,

            lower(`subject`) as `subject`,
        from {{ ref("snapshot_iready__instructional_usage_data") }}
    ),

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
            iready_usage pivot (
                max(last_week_lessons_passed) as n_lessons_passed,
                max(last_week_percent_lessons_passed) as pct_lessons_passed,
                max(last_week_time_on_task_min) as time_on_task for `subject`
                in ('reading', 'math')
            )
    ),
    identifiers as (
        select
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

            w.week_start_monday,
            w.week_end_sunday,
            w.date_count as days_in_session,
            w.quarter as term,

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

            cc.sections_section_number as course_section,
            cc.courses_course_name as course_name,
            cc.courses_course_number as course_number,
            cc.courses_credittype as course_credittype,
            cc.teachernumber as course_teachernumber,
            cc.teacher_lastfirst as course_teacher_name,

            hr.sections_section_number as homeroom_section,
            hr.teachernumber as homeroom_teachernumber,
            hr.teacher_lastfirst as homeroom_teacher_name,

            lc.head_of_school_preferred_name_lastfirst as head_of_school,

            if(co.lep_status, 'ML', 'Not ML') as ml_status,
            if(co.is_504, 'Has 504', 'No 504') as status_504,
            if(
                co.is_self_contained, 'Self-contained', 'Not self-contained'
            ) as self_contained_status,
            if(co.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

            safe_cast(r.assessment_id as string) as assessment_id,
            if(r.is_mastery, 1, 0) as is_mastery_int,

            concat(
                'https://kippteamschools.illuminateed.com/live/',
                '?assessment_id=' || r.assessment_id,
                '&page=Assessments_Overview_Controller'
            ) as illuminate_overview_link,

            concat(
                'https://kippteamschools.illuminateed.com/live/',
                '?page=PrebuiltReport_AssessmentResponseDistributionController',
                '&assessment_id=' || r.assessment_id,
                '&site_id=' || co.schoolid,
                '&code_prebuilt_id=370',
                '&action=showReport',
                '&create_student_group=t',
                '&fw_form_form_test=1',
                '&date=logged_in_date',
                '&group_by=overall',
                '&response_count_format=number',
                '&guid=21fa0ddf-1f3b-4918-80d9-f2088bcc7f48',
                '&reference_id=PR',
                '&state_id=31'
            ) as illuminate_response_frequency,

            concat(
                'https://kippteamschools.illuminateed.com/live/',
                '?page=PrebuiltReport_CodeBasedJasperController',
                '&_referrer_assessment_id=' || r.assessment_id,
                '&site_id=' || co.schoolid,
                '&debug=',
                '&jasper_prebuilt_id=308',
                '&fw_form_form_test=1',
                '&date=logged_in_date',
                '&matrix_position=2',
                '&matrix_order=1',
                '&matrix_group_by=1',
                '&gradebook_color_coding=1',
                '&matrix_stretch=1',
                '#report'
            ) as illuminate_matrix,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("int_powerschool__calendar_week") }} as w
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
            {{ ref("base_powerschool__course_enrollments") }} as cc
            on co.studentid = cc.cc_studentid
            and co.yearid = cc.cc_yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="cc") }}
            and r.subject_area = cc.illuminate_subject_area
            and not cc.is_dropped_section
            and cc.rn_student_year_illuminate_subject_desc = 1
        left join
            {{ ref("base_powerschool__course_enrollments") }} as hr
            on co.studentid = hr.cc_studentid
            and co.yearid = hr.cc_yearid
            and co.schoolid = hr.cc_schoolid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="hr") }}
            and hr.cc_course_number = 'HR'
            and not hr.is_dropped_section
            and hr.rn_course_number_year = 1
        left join
            {{ ref("int_people__leadership_crosswalk") }} as lc
            on co.schoolid = lc.home_work_location_powerschool_school_id
        where
            co.rn_year = 1
            and co.enroll_status = 0
            and co.academic_year >= {{ var("current_academic_year") - 1 }}
    )

/* ES/MS assessments */
select
    co.*,

    qbl.qbl,

    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,

    iw.n_lessons_passed_reading,
    iw.n_lessons_passed_math,
    iw.pct_lessons_passed_reading,
    iw.pct_lessons_passed_math,
    iw.time_on_task_reading,
    iw.time_on_task_math,

    sf.nj_student_tier,

    if(qbl.qbl is not null, true, false) as is_qbl,
from identifiers as co
left join
    {{ ref("int_reporting__student_filters") }} as sf
    on co.student_number = sf.student_number
    and co.academic_year = sf.academic_year
    and co.subject_area = sf.illuminate_subject_area
left join
    {{ ref("stg_assessments__qbls_power_standards") }} as qbl
    on co.academic_year = qbl.academic_year
    and co.region = qbl.region
    and co.grade_level = qbl.grade_level
    and co.response_type_code = qbl.standard_code
    and co.subject_area = qbl.illuminate_subject_area
    and qbl.qbl is not null
left join
    {{ ref("stg_assessments__academic_goals") }} as g
    on co.schoolid = g.school_id
    and co.grade_level = g.grade_level
    and co.academic_year = g.academic_year
    and co.subject_area = g.illuminate_subject_area
left join
    iready_weekly as iw
    on co.student_number = iw.student_number
    and co.academic_year = iw.academic_year
    and co.week_start_monday = iw.last_week_start_date
    and co.week_end_sunday = iw.last_week_end_date
    and iw.rn_iready_week = 1
where co.grade_level between 0 and 8

union all

/* HS assessments */
select
    co.*,

    qbl.qbl,

    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,

    null as n_lessons_passed_reading,
    null as n_lessons_passed_math,
    null as pct_lessons_passed_reading,
    null as pct_lessons_passed_math,
    null as time_on_task_reading,
    null as time_on_task_math,

    sf.nj_student_tier,

    if(qbl.qbl is not null, true, false) as is_qbl,
from identifiers as co
left join
    {{ ref("int_reporting__student_filters") }} as sf
    on co.student_number = sf.student_number
    and co.academic_year = sf.academic_year
    and co.course_credittype = sf.powerschool_credittype
left join
    {{ ref("stg_assessments__qbls_power_standards") }} as qbl
    on co.academic_year = qbl.academic_year
    and co.region = qbl.region
    and co.response_type_code = qbl.standard_code
    and co.subject_area = qbl.illuminate_subject_area
left join
    {{ ref("stg_assessments__academic_goals") }} as g
    on co.schoolid = g.school_id
    and co.academic_year = g.academic_year
    and co.subject_area = g.illuminate_subject_area
where co.grade_level between 9 and 12

union all
/* walkthrough data */
select
    null as student_number,
    null as student_name,

    w.academic_year,

    r.home_work_location_powerschool_school_id as schoolid,
    r.home_work_location_abbreviation as school,
    r.home_work_location_region as region,

    null as grade_level,
    null as enroll_status,
    null as cohort,

    cw.grade_band as school_level,

    null as gender,
    null as ethnicity,

    w.week_start_monday,
    w.week_end_sunday,
    w.date_count as days_in_session,
    w.quarter as term,

    o.rubric_name as title,

    null as scope,
    null as subject_area,

    o.observed_at as administered_at,

    null as date_taken,
    null as module_type,
    null as module_number,
    'walkthrough' as response_type,
    null as response_type_code,

    o.measurement_name as response_type_description,
    o.strand_name as response_type_root_description,
    o.observation_score as percent_correct,

    if(o.row_score = 1, true, false) as is_mastery,

    null as performance_band_label_number,
    null as performance_band_label,
    null as is_replacement,
    null as course_section,
    null as course_name,
    null as course_number,
    null as course_credittype,

    r.powerschool_teacher_number as course_teachernumber,
    t.lastfirst as course_teacher_name,

    null as homeroom_section,
    null as homeroom_teachernumber,
    null as homeroom_teacher_name,

    lc.head_of_school_preferred_name_lastfirst as head_of_school,

    null as ml_status,
    null as status_504,
    null as self_contained_status,
    null as iep_status,

    o.observation_id as assessment_id,
    o.row_score as is_mastery_int,

    null as illuminate_overview_link,
    null as illuminate_response_frequency,
    null as illuminate_matrix,

    null as qbl,
    null as grade_goal,
    null as school_goal,
    null as region_goal,
    null as organization_goal,
    null as n_lessons_passed_reading,
    null as n_lessons_passed_math,
    null as pct_lessons_passed_reading,
    null as pct_lessons_passed_math,
    null as time_on_task_reading,
    null as time_on_task_math,

    null as nj_student_tier,

    null as is_qbl,
from {{ ref("int_performance_management__observation_details") }} as o
inner join
    {{ ref("base_people__staff_roster") }} as r on o.employee_number = r.employee_number
left join
    {{ ref("int_powerschool__teachers") }} as t
    on r.powerschool_teacher_number = t.teachernumber
    and r.home_work_location_powerschool_school_id = t.schoolid
    and r.home_work_location_dagster_code_location
    = regexp_extract(t._dbt_source_relation, r'(kipp\w+)_')
inner join
    {{ ref("int_powerschool__calendar_week") }} as w
    on r.home_work_location_powerschool_school_id = w.schoolid
    and o.observed_at between w.week_start_monday and w.week_end_sunday
left join
    {{ ref("stg_people__location_crosswalk") }} as cw
    on r.home_work_location_name = cw.name
left join
    {{ ref("int_people__leadership_crosswalk") }} as lc
    on r.home_work_location_powerschool_school_id
    = lc.home_work_location_powerschool_school_id
where o.observation_type_abbreviation = 'WT'
