with
    enrollments_weeks as (
        select
            _dbt_source_relation,
            student_number,
            studentid,
            schoolid,
            school,
            region,
            grade_level,
            team,
            academic_year,
            yearid,
            deanslist_school_id,
            week_start_monday,
        from {{ ref("int_extracts__student_enrollments_weeks") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and is_enrolled_week
    ),

    enrollments as (
        select
            _dbt_source_relation,
            student_number,
            studentid,
            schoolid,
            school,
            region,
            grade_level,
            team,
            academic_year,
            yearid,
            advisor_teachernumber,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and rn_year = 1
            and enroll_status = 0
    ),

    /* ============================================================
     * TEACHER MANAGER LOOKUP — homeroom advisor's "reports to"
     * ============================================================ */
    team_manager_raw as (
        select
            e.school,
            e.team,
            sr.reports_to_formatted_name as manager,
        from enrollments as e
        left join
            {{ ref("int_people__staff_roster") }} as sr
            on e.advisor_teachernumber = sr.powerschool_teacher_number
    ),

    team_manager as (
        {{
            dbt_utils.deduplicate(
                relation="team_manager_raw",
                partition_by="school, team",
                order_by="manager",
            )
        }}
    ),

    /* ============================================================
     * ATTENDANCE — ADA and Chronic Absence (weekly, by homeroom/grade)
     * ============================================================ */
    ada_running as (
        select
            student_number,
            academic_year,
            week_start_monday,
            ada_running,
        from {{ ref("int_topline__ada_running_weekly") }}
        where academic_year = {{ var("current_academic_year") }}
    ),

    ada_by_student_week as (
        select
            ew.region,
            ew.school,
            ew.grade_level,
            ew.team,
            ew.week_start_monday,

            ar.ada_running,
            if(ar.ada_running <= 0.9, 1.0, 0.0) as is_chronic_absent,
        from enrollments_weeks as ew
        left join
            ada_running as ar
            on ew.student_number = ar.student_number
            and ew.academic_year = ar.academic_year
            and ew.week_start_monday = ar.week_start_monday
    ),

    ada_homeroom_week as (
        select
            asbw.region,
            asbw.school,
            asbw.team,
            asbw.week_start_monday,

            tm.manager,

            avg(asbw.ada_running) as metric_value,
        from ada_by_student_week as asbw
        left join
            team_manager as tm
            on asbw.school = tm.school
            and asbw.team = tm.team
        where asbw.ada_running is not null
        group by
            asbw.region,
            asbw.school,
            asbw.team,
            asbw.week_start_monday,
            tm.manager
    ),

    ada_gradelevel_week as (
        select
            region,
            school,
            grade_level,
            week_start_monday,

            avg(ada_running) as metric_value,
        from ada_by_student_week
        where ada_running is not null
        group by region, school, grade_level, week_start_monday
    ),

    chronic_homeroom_week as (
        select
            asbw.region,
            asbw.school,
            asbw.team,
            asbw.week_start_monday,

            tm.manager,

            avg(
                if(asbw.ada_running is not null, asbw.is_chronic_absent, null)
            ) as metric_value,
        from ada_by_student_week as asbw
        left join
            team_manager as tm
            on asbw.school = tm.school
            and asbw.team = tm.team
        group by
            asbw.region,
            asbw.school,
            asbw.team,
            asbw.week_start_monday,
            tm.manager
    ),

    chronic_gradelevel_week as (
        select
            region,
            school,
            grade_level,
            week_start_monday,

            avg(if(ada_running is not null, is_chronic_absent, null)) as metric_value,
        from ada_by_student_week
        group by region, school, grade_level, week_start_monday
    ),

    /* ============================================================
     * ASSESSMENT — Internal formative proficiency (weekly, by homeroom/grade)
     * ============================================================ */
    assessment_responses as (
        select
            powerschool_student_number,
            academic_year,
            discipline,
            module_code,

            date_trunc(administered_at, week(monday)) as week_start_monday,
            if(is_mastery, 1.0, 0.0) as is_mastery_num,
        from {{ ref("int_assessments__response_rollup") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and response_type = 'overall'
            and module_type in ('QA', 'MQQ', 'CRQ', 'TP')
            and is_mastery is not null
            and discipline in ('ELA', 'Math')
    ),

    proficiency_homeroom_week as (
        select
            e.region,
            e.school,
            e.team,
            a.week_start_monday,
            a.discipline,
            a.module_code,

            tm.manager,

            avg(a.is_mastery_num) as metric_value,
        from assessment_responses as a
        inner join
            enrollments as e
            on a.powerschool_student_number = e.student_number
            and a.academic_year = e.academic_year
        left join
            team_manager as tm
            on e.school = tm.school
            and e.team = tm.team
        group by
            e.region,
            e.school,
            e.team,
            a.week_start_monday,
            a.discipline,
            a.module_code,
            tm.manager
    ),

    proficiency_gradelevel_week as (
        select
            e.region,
            e.school,
            e.grade_level,
            a.week_start_monday,
            a.discipline,
            a.module_code,

            avg(a.is_mastery_num) as metric_value,
        from assessment_responses as a
        inner join
            enrollments as e
            on a.powerschool_student_number = e.student_number
            and a.academic_year = e.academic_year
        group by
            e.region,
            e.school,
            e.grade_level,
            a.week_start_monday,
            a.discipline,
            a.module_code
    ),

    /* ============================================================
     * CULTURE — DeansList referral counts by tier (weekly, by homeroom/grade)
     * ============================================================ */
    dl_incidents as (
        select
            student_school_id,
            create_ts_academic_year,
            school_id as deanslist_school_id,
            incident_id,
            referral_tier,

            date_trunc(start_date, week(monday)) as week_start_monday,
        from {{ ref("int_deanslist__incidents__penalties") }}
        where
            create_ts_academic_year = {{ var("current_academic_year") }}
            and referral_tier not in ('Non-Behavioral', 'Social Work')
            and start_date is not null
    ),

    dl_homeroom_week as (
        select
            ew.region,
            ew.school,
            ew.team,
            ew.week_start_monday,

            tm.manager,

            count(
                distinct if(dl.referral_tier = 'High', dl.incident_id, null)
            ) as referral_high,
            count(
                distinct if(dl.referral_tier = 'Middle', dl.incident_id, null)
            ) as referral_middle,
            count(
                distinct if(dl.referral_tier = 'low', dl.incident_id, null)
            ) as referral_low,
            count(distinct dl.incident_id) as referral_all,
        from enrollments_weeks as ew
        left join
            dl_incidents as dl
            on ew.student_number = dl.student_school_id
            and ew.academic_year = dl.create_ts_academic_year
            and ew.deanslist_school_id = dl.deanslist_school_id
            and ew.week_start_monday = dl.week_start_monday
        left join
            team_manager as tm
            on ew.school = tm.school
            and ew.team = tm.team
        group by ew.region, ew.school, ew.team, ew.week_start_monday, tm.manager
    ),

    dl_gradelevel_week as (
        select
            ew.region,
            ew.school,
            ew.grade_level,
            ew.week_start_monday,

            count(
                distinct if(dl.referral_tier = 'High', dl.incident_id, null)
            ) as referral_high,
            count(
                distinct if(dl.referral_tier = 'Middle', dl.incident_id, null)
            ) as referral_middle,
            count(
                distinct if(dl.referral_tier = 'low', dl.incident_id, null)
            ) as referral_low,
            count(distinct dl.incident_id) as referral_all,
        from enrollments_weeks as ew
        left join
            dl_incidents as dl
            on ew.student_number = dl.student_school_id
            and ew.academic_year = dl.create_ts_academic_year
            and ew.deanslist_school_id = dl.deanslist_school_id
            and ew.week_start_monday = dl.week_start_monday
        group by ew.region, ew.school, ew.grade_level, ew.week_start_monday
    ),

    /* ============================================================
     * GRADES — Failure rate by academic section + term
     * ============================================================ */
    section_enrollments as (
        select
            enr._dbt_source_relation,
            enr.cc_studentid,
            enr.cc_yearid,
            enr.cc_sectionid,
            enr.cc_academic_year,
            enr.cc_schoolid,
            enr.cc_dateenrolled,
            enr.courses_course_name,
            enr.sections_section_number,
        from {{ ref("base_powerschool__course_enrollments") }} as enr
        where
            enr.cc_academic_year = {{ var("current_academic_year") }}
            and not enr.is_dropped_course
            and enr.courses_credittype not in ('ADVISORY', 'LNCH')
    ),

    section_enrollments_dedup as (
        {{
            dbt_utils.deduplicate(
                relation="section_enrollments",
                partition_by="_dbt_source_relation, cc_studentid, cc_academic_year, cc_sectionid",
                order_by="cc_dateenrolled desc",
            )
        }}
    ),

    section_school_context as (
        select distinct
            _dbt_source_relation,
            studentid,
            schoolid,
            school,
            region,
        from {{ ref("int_extracts__student_enrollments") }}
        where academic_year = {{ var("current_academic_year") }}
    ),

    section_teacher_manager_raw as (
        select
            enr._dbt_source_relation,
            enr.cc_sectionid,
            sr.reports_to_formatted_name as manager,
        from section_enrollments_dedup as enr
        left join
            {{ ref("base_powerschool__sections") }} as sec
            on enr.cc_sectionid = sec.sections_id
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="sec") }}
        left join
            {{ ref("int_people__staff_roster") }} as sr
            on sec.teachernumber = sr.powerschool_teacher_number
    ),

    section_teacher_manager as (
        {{
            dbt_utils.deduplicate(
                relation="section_teacher_manager_raw",
                partition_by="_dbt_source_relation, cc_sectionid",
                order_by="manager",
            )
        }}
    ),

    section_grades_raw as (
        select
            sc.region,
            sc.school,
            enr.sections_section_number,
            enr.courses_course_name,
            fg.storecode,
            stm.manager,

            count(enr.cc_studentid) as n_students,
            countif(fg.y1_letter_grade_adjusted in ('F', 'F*')) as n_failing,
        from section_enrollments_dedup as enr
        left join
            {{ ref("int_powerschool__final_grades_pivot") }} as fg
            on enr.cc_studentid = fg.studentid
            and enr.cc_yearid = fg.yearid
            and enr.cc_sectionid = fg.sectionid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="fg") }}
        inner join
            section_school_context as sc
            on enr.cc_studentid = sc.studentid
            and enr.cc_schoolid = sc.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="sc") }}
        left join
            section_teacher_manager as stm
            on enr.cc_sectionid = stm.cc_sectionid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="stm") }}
        where fg.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
        group by
            sc.region,
            sc.school,
            enr.sections_section_number,
            enr.courses_course_name,
            fg.storecode,
            stm.manager
    ),

    /* ============================================================
     * ACADEMICS — Avg weighted Y1 GPA by homeroom + term
     * ============================================================ */
    gpa_homeroom_term as (
        select
            e.region,
            e.school,
            e.team,
            g.term_name,

            tm.manager,

            avg(g.gpa_y1) as metric_value,
        from enrollments as e
        left join
            {{ ref("int_powerschool__gpa_term") }} as g
            on e.studentid = g.studentid
            and e.yearid = g.yearid
            and e.schoolid = g.schoolid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="g") }}
        left join
            team_manager as tm
            on e.school = tm.school
            and e.team = tm.team
        where g.gpa_y1 is not null
        group by e.region, e.school, e.team, g.term_name, tm.manager
    )

/* ============================================================
 * FINAL UNION — all metrics in long format
 * ============================================================ */

/* 1. ADA by homeroom + week */
select
    'Attendance' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    'Weekly ADA' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Homeroom' as grain_type,
    team as grain,
    manager,
    metric_value as value,
from ada_homeroom_week

union all

/* 2. ADA by grade level + week */
select
    'Attendance' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    'Weekly ADA' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Grade Level' as grain_type,
    cast(grade_level as string) as grain,
    cast(null as string) as manager,
    metric_value as value,
from ada_gradelevel_week

union all

/* 3. % Chronically Absent (ADA <= 90%) by homeroom + week */
select
    'Attendance' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    '% Chronically Absent (ADA <= 90%)' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Homeroom' as grain_type,
    team as grain,
    manager,
    metric_value as value,
from chronic_homeroom_week

union all

/* 4. % Chronically Absent (ADA <= 90%) by grade level + week */
select
    'Attendance' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    '% Chronically Absent (ADA <= 90%)' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Grade Level' as grain_type,
    cast(grade_level as string) as grain,
    cast(null as string) as manager,
    metric_value as value,
from chronic_gradelevel_week

union all

/* 5. Assessment proficiency by homeroom + week */
select
    'Assessment' as domain,
    discipline,
    cast(null as string) as course_name,
    module_code,
    'Proficiency (Mastery Rate)' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Homeroom' as grain_type,
    team as grain,
    manager,
    metric_value as value,
from proficiency_homeroom_week

union all

/* 6. Assessment proficiency by grade level + week */
select
    'Assessment' as domain,
    discipline,
    cast(null as string) as course_name,
    module_code,
    'Proficiency (Mastery Rate)' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Grade Level' as grain_type,
    cast(grade_level as string) as grain,
    cast(null as string) as manager,
    metric_value as value,
from proficiency_gradelevel_week

union all

/* 7. DeansList referrals - All by homeroom + week */
select
    'Culture' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    'Referrals - All' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Homeroom' as grain_type,
    team as grain,
    manager,
    cast(referral_all as float64) as value,
from dl_homeroom_week

union all

/* 8. DeansList referrals - High by homeroom + week */
select
    'Culture' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    'Referrals - High' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Homeroom' as grain_type,
    team as grain,
    manager,
    cast(referral_high as float64) as value,
from dl_homeroom_week

union all

/* 9. DeansList referrals - Middle by homeroom + week */
select
    'Culture' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    'Referrals - Middle' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Homeroom' as grain_type,
    team as grain,
    manager,
    cast(referral_middle as float64) as value,
from dl_homeroom_week

union all

/* 10. DeansList referrals - Low by homeroom + week */
select
    'Culture' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    'Referrals - Low' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Homeroom' as grain_type,
    team as grain,
    manager,
    cast(referral_low as float64) as value,
from dl_homeroom_week

union all

/* 11. DeansList referrals - All by grade level + week */
select
    'Culture' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    'Referrals - All' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Grade Level' as grain_type,
    cast(grade_level as string) as grain,
    cast(null as string) as manager,
    cast(referral_all as float64) as value,
from dl_gradelevel_week

union all

/* 12. DeansList referrals - High by grade level + week */
select
    'Culture' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    'Referrals - High' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Grade Level' as grain_type,
    cast(grade_level as string) as grain,
    cast(null as string) as manager,
    cast(referral_high as float64) as value,
from dl_gradelevel_week

union all

/* 13. DeansList referrals - Middle by grade level + week */
select
    'Culture' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    'Referrals - Middle' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Grade Level' as grain_type,
    cast(grade_level as string) as grain,
    cast(null as string) as manager,
    cast(referral_middle as float64) as value,
from dl_gradelevel_week

union all

/* 14. DeansList referrals - Low by grade level + week */
select
    'Culture' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    'Referrals - Low' as metric,
    concat('week of ', format_date('%Y-%m-%d', week_start_monday)) as time_scale,
    region,
    school,
    'Grade Level' as grain_type,
    cast(grade_level as string) as grain,
    cast(null as string) as manager,
    cast(referral_low as float64) as value,
from dl_gradelevel_week

union all

/* 15. Failure rate by section + term */
select
    'Grades' as domain,
    cast(null as string) as discipline,
    courses_course_name as course_name,
    cast(null as string) as module_code,
    'Failure Rate (Y1)' as metric,
    storecode as time_scale,
    region,
    school,
    'Section' as grain_type,
    sections_section_number as grain,
    manager,
    safe_divide(n_failing, n_students) as value,
from section_grades_raw

union all

/* 16. Avg weighted Y1 GPA by homeroom + term */
select
    'Academics' as domain,
    cast(null as string) as discipline,
    cast(null as string) as course_name,
    cast(null as string) as module_code,
    'Avg Y1 GPA (Weighted)' as metric,
    term_name as time_scale,
    region,
    school,
    'Homeroom' as grain_type,
    team as grain,
    manager,
    metric_value as value,
from gpa_homeroom_term
