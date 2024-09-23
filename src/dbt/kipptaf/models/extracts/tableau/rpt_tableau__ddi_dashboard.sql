with
    iready_weekly as (
        select
            il.academic_year_int,
            il.student_id,
            lower(il.subject) as subject,

            cw.powerschool_school_id,

            pw.week_start_monday,

            if(
                sum(il.passed_or_not_passed_numeric) >= 2, 1, 0
            ) as is_pass_2_lessons_int,
            if(
                sum(il.passed_or_not_passed_numeric) >= 4, 1, 0
            ) as is_pass_4_lessons_int,
        from {{ ref("stg_iready__personalized_instruction_by_lesson") }} as il
        inner join
            {{ ref("stg_people__location_crosswalk") }} as cw on il.school = cw.name
        inner join
            {{ ref("int_powerschool__calendar_week") }} as pw
            on il.academic_year_int = pw.academic_year
            and cw.powerschool_school_id = pw.schoolid
            and il.completion_date between pw.week_start_monday and pw.week_end_sunday
        group by
            il.academic_year_int,
            il.student_id,
            il.subject,
            cw.powerschool_school_id,
            pw.week_start_monday
    ),

    iready_pivot as (
        select
            academic_year_int,
            student_id,
            powerschool_school_id,
            week_start_monday,
            is_pass_2_lessons_int_reading,
            is_pass_4_lessons_int_reading,
            is_pass_2_lessons_int_math,
            is_pass_4_lessons_int_math,
        from
            iready_weekly pivot (
                max(is_pass_2_lessons_int) as is_pass_2_lessons_int,
                max(is_pass_4_lessons_int) as is_pass_4_lessons_int for subject
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

            sc.title,
            sc.subject_area,
            sc.administered_at,
            sc.module_type,
            sc.module_code,

            r.date_taken,
            r.response_type,
            r.response_type_code,
            r.response_type_description,
            r.response_type_root_description,
            r.percent_correct,
            r.is_mastery,
            r.performance_band_label_number,
            r.performance_band_label,
            r.is_replacement,

            sd.standard_domain,

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

            if(
                current_date('America/New_York')
                between w.week_start_monday and w.week_end_sunday,
                true,
                false
            ) as is_current_week,

            safe_cast(r.assessment_id as string) as assessment_id,
            case
                when r.is_mastery then 1 when not r.is_mastery then 0
            end as is_mastery_int,
            if(r.date_taken is not null, 1, 0) as is_complete,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("int_powerschool__calendar_week") }} as w
            on co.academic_year = w.academic_year
            and co.schoolid = w.schoolid
            and w.week_end_sunday between co.entrydate and co.exitdate
        left join
            {{ ref("int_assessments__scaffold") }} as sc
            on co.student_number = sc.powerschool_student_number
            and co.academic_year = sc.academic_year
            and co.region = sc.region
            and sc.administered_at between w.week_start_monday and w.week_end_sunday
        left join
            {{ ref("int_assessments__response_rollup") }} as r
            on sc.powerschool_student_number = r.powerschool_student_number
            and sc.assessment_id = r.assessment_id
        left join
            {{ ref("stg_assessments__standard_domains") }} as sd
            on r.response_type_code = sd.standard_code
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
            co.enroll_status = 0
            and co.academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    microgoals as (
        select
            employee_number,
            week_start_monday,
            string_agg(goal_name, ', ') as microgoals,
        from
            (
                select
                    u.internal_id_int as employee_number,

                    m.goal_name,

                    date_add(
                        date(timestamp_trunc(timestamp(a.created), week)),
                        interval 1 day
                    ) as week_start_monday,
                from {{ ref("stg_schoolmint_grow__users") }} as u
                left join
                    {{ ref("stg_schoolmint_grow__assignments") }} as a
                    on u.user_id = a.user_id
                left join
                    {{ ref("stg_schoolmint_grow__assignments__tags") }} as t
                    on a.assignment_id = t.assignment_id
                left join
                    {{ ref("stg_schoolmint_grow__microgoals") }} as m
                    on t.tag_id = m.goal_tag_id
                where m.goal_code is not null
            )
        group by employee_number, week_start_monday
    )

/* ES/MS assessments */
select
    co.*,

    qbl.qbl,

    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,

    sf.nj_student_tier,
    sf.dibels_most_recent_composite,

    if(qbl.qbl is not null, true, false) as is_qbl,

    coalesce(ip.is_pass_2_lessons_int_reading, 0) as is_passed_iready_2plus_reading_int,
    coalesce(ip.is_pass_4_lessons_int_reading, 0) as is_passed_iready_4plus_reading_int,
    coalesce(ip.is_pass_2_lessons_int_math, 0) as is_passed_iready_2plus_math_int,
    coalesce(ip.is_pass_4_lessons_int_math, 0) as is_passed_iready_4plus_math_int,
from identifiers as co
left join
    {{ ref("int_reporting__student_filters") }} as sf
    on co.student_number = sf.student_number
    and co.academic_year = sf.academic_year
    and co.subject_area = sf.illuminate_subject_area
left join
    {{ ref("stg_assessments__qbls_power_standards") }} as qbl
    on co.academic_year = qbl.academic_year
    and co.term = qbl.term_name
    and co.region = qbl.region
    and co.grade_level = qbl.grade_level
    and co.response_type_code = qbl.standard_code
    and co.subject_area = qbl.illuminate_subject_area
    and qbl.qbl is not null
left join
    {{ ref("int_assessments__academic_goals") }} as g
    on co.schoolid = g.school_id
    and co.grade_level = g.grade_level
    and co.academic_year = g.academic_year
    and co.subject_area = g.illuminate_subject_area
left join
    iready_pivot as ip
    on co.student_number = ip.student_id
    and co.academic_year = ip.academic_year_int
    and co.week_start_monday = ip.week_start_monday
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

    sf.nj_student_tier,
    null as dibels_most_recent_composite,

    if(qbl.qbl is not null, true, false) as is_qbl,

    null as is_passed_iready_2plus_reading_int,
    null as is_passed_iready_4plus_reading_int,
    null as is_passed_iready_2plus_math_int,
    null as is_passed_iready_4plus_math_int,
from identifiers as co
left join
    {{ ref("int_reporting__student_filters") }} as sf
    on co.student_number = sf.student_number
    and co.academic_year = sf.academic_year
    and co.course_credittype = sf.powerschool_credittype
left join
    {{ ref("stg_assessments__qbls_power_standards") }} as qbl
    on co.academic_year = qbl.academic_year
    and co.term = qbl.term_name
    and co.region = qbl.region
    and co.response_type_code = qbl.standard_code
    and co.subject_area = qbl.illuminate_subject_area
left join
    {{ ref("int_assessments__academic_goals") }} as g
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

    case
        when r.home_work_location_region = 'TEAM Academy Charter School'
        then 'Newark'
        when r.home_work_location_region = 'KIPP Cooper Norcross Academy'
        then 'Camden'
        when r.home_work_location_region = 'KIPP Miami'
        then 'Miami'
        else r.home_work_location_region
    end as region,

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
    m.microgoals as subject_area,
    o.observed_at as administered_at,
    null as module_type,
    null as module_code,

    null as date_taken,
    'walkthrough' as response_type,
    null as response_type_code,
    o.measurement_name as response_type_description,
    o.strand_name as response_type_root_description,
    o.observation_score as percent_correct,
    if(o.row_score = 1, true, false) as is_mastery,
    null as performance_band_label_number,
    null as performance_band_label,
    null as is_replacement,

    null as standard_domain,
    null as course_section,
    null as course_name,
    null as course_number,
    null as course_credittype,

    r.powerschool_teacher_number as course_teachernumber,
    t.lastfirst as course_teacher_name,

    null as homeroom_section,
    null as homeroom_teachernumber,
    r.report_to_user_principal_name as homeroom_teacher_name,

    lc.head_of_school_preferred_name_lastfirst as head_of_school,

    null as ml_status,
    null as status_504,
    null as self_contained_status,
    null as iep_status,

    if(
        current_date('America/New_York')
        between w.week_start_monday and w.week_end_sunday,
        true,
        false
    ) as is_current_week,

    o.observation_id as assessment_id,
    o.row_score as is_mastery_int,
    null as is_complete,

    null as qbl,
    null as grade_goal,
    null as school_goal,
    null as region_goal,
    null as organization_goal,

    null as nj_student_tier,
    null as dibels_most_recent_composite,

    null as is_qbl,

    null as is_passed_iready_2plus_reading_int,
    null as is_passed_iready_4plus_reading_int,
    null as is_passed_iready_2plus_math_int,
    null as is_passed_iready_4plus_math_int,
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
left join
    microgoals as m
    on r.employee_number = m.employee_number
    and w.week_start_monday = m.week_start_monday
where o.observation_type_abbreviation = 'WT'
