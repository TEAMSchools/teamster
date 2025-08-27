with
    iready_weekly as (
        select
            il.academic_year_int,
            il.student_id,

            cw.powerschool_school_id,

            pw.week_start_monday,

            lower(il.subject) as `subject`,

            sum(il.passed_or_not_passed_numeric) as total_iready_lessons_passed,

            if(
                sum(il.passed_or_not_passed_numeric) >= 2, 1, 0
            ) as is_pass_2_lessons_int,

            if(
                sum(il.passed_or_not_passed_numeric) >= 4, 1, 0
            ) as is_pass_4_lessons_int,
        from {{ ref("int_iready__instruction_by_lesson_union") }} as il
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
            total_iready_lessons_passed_reading,
            is_pass_2_lessons_int_reading,
            is_pass_4_lessons_int_reading,
            total_iready_lessons_passed_math,
            is_pass_2_lessons_int_math,
            is_pass_4_lessons_int_math,
        from
            iready_weekly pivot (
                max(total_iready_lessons_passed) as total_iready_lessons_passed,
                max(is_pass_2_lessons_int) as is_pass_2_lessons_int,
                max(is_pass_4_lessons_int) as is_pass_4_lessons_int for `subject`
                in ('reading', 'math')
            )
    ),

    identifiers as (
        select
            co.student_number,
            co.student_name,
            co.academic_year,
            co.schoolid,
            co.school,
            co.region,
            co.grade_level,
            co.enroll_status,
            co.cohort,
            co.school_level,
            co.gender,
            co.ethnicity,
            co.year_in_network,
            co.is_self_contained,
            co.advisory_section_number as homeroom_section,
            co.advisor_lastfirst as homeroom_teacher_name,
            co.advisor_teachernumber as homeroom_teachernumber,

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
            cc.is_foundations,

            sf.dibels_most_recent_composite,
            sf.state_test_proficiency,
            sf.is_exempt_iready,

            lc.head_of_school_preferred_name_lastfirst as head_of_school,

            coalesce(sf.nj_student_tier, 'Unbucketed') as nj_student_tier,

            cast(r.assessment_id as string) as assessment_id,

            if(co.lep_status, 'ML', 'Not ML') as ml_status,
            if(co.is_504, 'Has 504', 'No 504') as status_504,
            if(
                co.is_self_contained, 'Self-contained', 'Not self-contained'
            ) as self_contained_status,
            if(co.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,
            coalesce(co.gifted_and_talented, 'N') as gifted_and_talented,

            if(
                current_date('{{ var("local_timezone") }}')
                between w.week_start_monday and w.week_end_sunday,
                true,
                false
            ) as is_current_week,

            if(r.date_taken is not null, 1, 0) as is_complete,

            case
                when r.is_mastery then 1 when not r.is_mastery then 0
            end as is_mastery_int,
        from {{ ref("int_extracts__student_enrollments") }} as co
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
            {{ ref("int_extracts__student_enrollments_subjects") }} as sf
            on co.student_number = sf.student_number
            and co.academic_year = sf.academic_year
            and cc.courses_credittype = sf.powerschool_credittype
            and sf.rn_year = 1
        left join
            {{ ref("int_people__leadership_crosswalk") }} as lc
            on co.schoolid = lc.home_work_location_powerschool_school_id
        where
            co.enroll_status = 0
            and co.academic_year >= {{ var("current_academic_year") - 2 }}
            and not co.is_out_of_district
            {# TODO: Remove SY26 #}
            /* Manual filter to avoid dashboard roll-up */
            and sc.module_type != 'WPP'
    ),

    microgoals_long as (
        select
            u.internal_id_int as employee_number,

            m.goal_name,

            date_add(
                date(timestamp_trunc(timestamp(a.created), week)), interval 1 day
            ) as week_start_monday,
        from {{ ref("stg_schoolmint_grow__users") }} as u
        left join
            {{ ref("stg_schoolmint_grow__assignments") }} as a on u.user_id = a.user_id
        left join
            {{ ref("stg_schoolmint_grow__assignments__tags") }} as t
            on a.assignment_id = t.assignment_id
        left join
            {{ ref("stg_schoolmint_grow__microgoals") }} as m
            on t.tag_id = m.goal_tag_id
        where m.goal_code is not null
    ),

    microgoals as (
        select
            employee_number,
            week_start_monday,

            string_agg(goal_name, ', ') as microgoals,
        from microgoals_long
        group by employee_number, week_start_monday
    )

/* ES/MS assessments */
select
    co.student_number,
    co.student_name,
    co.academic_year,
    co.schoolid,
    co.school,
    co.region,
    co.grade_level,
    co.enroll_status,
    co.cohort,
    co.school_level,
    co.gender,
    co.ethnicity,
    co.year_in_network,
    co.is_self_contained,
    co.week_start_monday,
    co.week_end_sunday,
    co.days_in_session,
    co.term,
    co.title,
    co.subject_area,
    co.administered_at,
    co.module_type,
    co.module_code,
    co.date_taken,
    co.response_type,
    co.response_type_code,
    co.response_type_description,
    co.response_type_root_description,
    co.percent_correct,
    co.is_mastery,
    co.performance_band_label_number,
    co.performance_band_label,
    co.is_replacement,
    co.standard_domain,
    co.course_section,
    co.course_name,
    co.course_number,
    co.course_credittype,
    co.course_teachernumber,
    co.course_teacher_name,
    co.is_foundations,
    co.homeroom_section,
    co.homeroom_teachernumber,
    co.homeroom_teacher_name,
    co.head_of_school,
    co.ml_status,
    co.status_504,
    co.self_contained_status,
    co.iep_status,
    co.gifted_and_talented,
    co.is_current_week,
    co.assessment_id,
    co.is_mastery_int,
    co.is_complete,
    co.dibels_most_recent_composite,
    co.state_test_proficiency,
    co.is_exempt_iready,
    co.nj_student_tier,

    qbls.qbl,

    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,

    coalesce(
        ip.total_iready_lessons_passed_reading, 0
    ) as total_iready_lessons_passed_reading,
    coalesce(
        ip.total_iready_lessons_passed_math, 0
    ) as total_iready_lessons_passed_math,

    if(qbls.qbl is not null, true, false) as is_qbl,

    coalesce(ip.is_pass_2_lessons_int_reading, 0) as is_passed_iready_2plus_reading_int,
    coalesce(ip.is_pass_4_lessons_int_reading, 0) as is_passed_iready_4plus_reading_int,
    coalesce(ip.is_pass_2_lessons_int_math, 0) as is_passed_iready_2plus_math_int,
    coalesce(ip.is_pass_4_lessons_int_math, 0) as is_passed_iready_4plus_math_int,
from identifiers as co
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as sf
    on co.student_number = sf.student_number
    and co.academic_year = sf.academic_year
    and co.subject_area = sf.illuminate_subject_area
    and sf.rn_year = 1
left join
    {{ ref("stg_assessments__qbls_power_standards") }} as qbls
    on co.academic_year = qbls.academic_year
    and co.term = qbls.term_name
    and co.region = qbls.region
    and co.grade_level = qbls.grade_level
    and co.response_type_code = qbls.standard_code
    and co.subject_area = qbls.illuminate_subject_area
    and qbls.qbl is not null
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
    co.student_number,
    co.student_name,
    co.academic_year,
    co.schoolid,
    co.school,
    co.region,
    co.grade_level,
    co.enroll_status,
    co.cohort,
    co.school_level,
    co.gender,
    co.ethnicity,
    co.year_in_network,
    co.is_self_contained,
    co.week_start_monday,
    co.week_end_sunday,
    co.days_in_session,
    co.term,
    co.title,
    co.subject_area,
    co.administered_at,
    co.module_type,
    co.module_code,
    co.date_taken,
    co.response_type,
    co.response_type_code,
    co.response_type_description,
    co.response_type_root_description,
    co.percent_correct,
    co.is_mastery,
    co.performance_band_label_number,
    co.performance_band_label,
    co.is_replacement,
    co.standard_domain,
    co.course_section,
    co.course_name,
    co.course_number,
    co.course_credittype,
    co.course_teachernumber,
    co.course_teacher_name,
    co.is_foundations,
    co.homeroom_section,
    co.homeroom_teachernumber,
    co.homeroom_teacher_name,
    co.head_of_school,
    co.ml_status,
    co.status_504,
    co.self_contained_status,
    co.iep_status,
    co.gifted_and_talented,
    co.is_current_week,
    co.assessment_id,
    co.is_mastery_int,
    co.is_complete,
    co.dibels_most_recent_composite,
    co.state_test_proficiency,
    co.is_exempt_iready,
    co.nj_student_tier,

    qbls.qbl,

    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,

    null as total_iready_lessons_passed_reading,
    null as total_iready_lessons_passed_math,

    if(qbls.qbl is not null, true, false) as is_qbl,

    null as is_passed_iready_2plus_reading_int,
    null as is_passed_iready_4plus_reading_int,
    null as is_passed_iready_2plus_math_int,
    null as is_passed_iready_4plus_math_int,
from identifiers as co
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as sf
    on co.student_number = sf.student_number
    and co.academic_year = sf.academic_year
    and co.course_credittype = sf.assessment_dashboard_join
    and sf.rn_year = 1
left join
    {{ ref("stg_assessments__qbls_power_standards") }} as qbls
    on co.academic_year = qbls.academic_year
    and co.term = qbls.term_name
    and co.region = qbls.region
    and co.response_type_code = qbls.standard_code
    and co.subject_area = qbls.illuminate_subject_area
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
    r.sam_account_name as student_name,

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
    null as year_in_network,
    null as is_self_contained,

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

    case
        when o.row_score = 1 then true when o.row_score = 0 then false
    end as is_mastery,

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
    null as is_foundations,

    r.reports_to_sam_account_name as homeroom_teacher_name,

    lc.head_of_school_preferred_name_lastfirst as head_of_school,

    null as ml_status,
    null as status_504,
    null as self_contained_status,
    null as iep_status,
    null as gifted_and_talented,

    if(
        current_date('{{ var("local_timezone") }}')
        between w.week_start_monday and w.week_end_sunday,
        true,
        false
    ) as is_current_week,

    o.observation_id as assessment_id,
    o.row_score as is_mastery_int,

    null as is_complete,
    null as dibels_most_recent_composite,
    null as state_test_proficiency,
    null as is_exempt_iready,
    null as nj_student_tier,
    null as qbl,
    null as grade_goal,
    null as school_goal,
    null as region_goal,
    null as organization_goal,
    null as total_iready_lessons_passed_reading,
    null as total_iready_lessons_passed_math,
    null as is_qbl,
    null as is_passed_iready_2plus_reading_int,
    null as is_passed_iready_4plus_reading_int,
    null as is_passed_iready_2plus_math_int,
    null as is_passed_iready_4plus_math_int,
from {{ ref("int_performance_management__observation_details") }} as o
inner join
    {{ ref("int_people__staff_roster") }} as r on o.employee_number = r.employee_number
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
where
    o.observation_type_abbreviation = 'WT'
    and w.academic_year = {{ var("current_academic_year") - 1 }}
