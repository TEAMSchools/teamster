{% set quarter = ["Q1", "Q2", "Q3", "Q4", "Y1"] %}
{% set exempt_courses = [
    "LOG20",
    "LOG22999XL",
    "LOG9",
    "LOG100",
    "LOG1010",
    "LOG11",
    "LOG12",
    "LOG300",
    "SEM22106G1",
    "SEM22106S1",
] %}

with
    student_roster as (
        select
            enr._dbt_source_relation,
            enr.academic_year,
            enr.yearid,
            enr.region,
            enr.school_level,
            enr.schoolid,
            enr.school_abbreviation as school,
            enr.studentid,
            enr.student_number,
            enr.lastfirst,
            enr.gender,
            enr.enroll_status,
            enr.grade_level,
            enr.ethnicity,
            enr.cohort,
            enr.year_in_school,
            enr.advisor_lastfirst as advisor_name,
            enr.is_out_of_district,
            enr.lep_status,
            enr.is_504,
            enr.is_self_contained as is_pathways,
            enr.lunch_status,
            enr.year_in_network,
            enr.is_retained_year,
            enr.is_retained_ever,
            enr.rn_undergrad,

            ktc.contact_id as salesforce_id,
            ktc.ktc_cohort,

            hos.head_of_school_preferred_name_lastfirst as hos,

            quarter,

            'Local' as roster_type,

            if(
                enr.school_level in ('ES', 'MS'), advisory_name, advisor_lastfirst
            ) as advisory,

            if(enr.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

            case
                when quarter in ('Q1', 'Q2')
                then 'S1'
                when quarter in ('Q3', 'Q4')
                then 'S2'
                else 'S#'  -- for Y1
            end as semester,

            case when sp.studentid is not null then 1 end as is_counseling_services,

            case when sa.studentid is not null then 1 end as is_student_athlete,

            round(ada.ada, 3) as ada,
        from {{ ref("base_powerschool__student_enrollments") }} as enr
        left join
            {{ ref("int_kippadb__roster") }} as ktc
            on enr.student_number = ktc.student_number
        left join
            {{ ref("int_powerschool__spenrollments") }} as sp
            on enr.studentid = sp.studentid
            and current_date('America/New_York') between sp.enter_date and sp.exit_date
            and sp.specprog_name = 'Counseling Services'
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="sp") }}
        left join
            {{ ref("int_powerschool__spenrollments") }} as sa
            on enr.studentid = sa.studentid
            and sa.specprog_name = 'Student Athlete'
            and current_date('America/New_York') between sa.enter_date and sa.exit_date
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="sa") }}
        left join
            {{ ref("int_powerschool__ada") }} as ada
            on enr.yearid = ada.yearid
            and enr.studentid = ada.studentid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="ada") }}
        left join
            {{ ref("int_people__leadership_crosswalk") }} as hos
            on enr.schoolid = hos.home_work_location_powerschool_school_id
        cross join unnest({{ quarter }}) as quarter
        where
            enr.rn_year = 1
            and enr.grade_level != 99
            and not enr.is_out_of_district
            and enr.academic_year = {{ var("current_academic_year") }}
    /*,

    transfer_roster as (
        select distinct
            tr._dbt_source_relation,
            tr.academic_year,
            tr.yearid,
            tr.studentid,
            tr.grade_level,

            'Q#' as quarter,
            'S#' as semester,

            'Transfer' as roster_type,

            coalesce(co.region, e1.region) as region,
            coalesce(co.school_level, e1.school_level) as school_level,
            coalesce(co.schoolid, e1.schoolid) as schoolid,
            coalesce(co.school, e1.school) as school,
            coalesce(co.student_number, e1.student_number) as student_number,
            coalesce(co.lastfirst, e1.lastfirst) as lastfirst,
            coalesce(co.gender, e1.gender) as gender,
            coalesce(co.enroll_status, e1.enroll_status) as enroll_status,
            coalesce(co.ethnicity, e1.ethnicity) as ethnicity,
            coalesce(co.cohort, e1.cohort) as cohort,
            coalesce(co.year_in_school, e1.year_in_school) as year_in_school,
            coalesce(co.advisor_name, e1.advisor_name) as advisor_name,
            coalesce(
                co.is_out_of_district, e1.is_out_of_district
            ) as is_out_of_district,
            coalesce(co.lep_status, e1.lep_status) as lep_status,
            coalesce(co.is_504, e1.is_504) as is_504,
            coalesce(co.is_pathways, e1.is_pathways) as is_pathways,
            coalesce(co.lunch_status, e1.lunch_status) as lunch_status,
            coalesce(co.year_in_network, e1.year_in_network) as year_in_network,
            coalesce(co.is_retained_year, e1.is_retained_year) as is_retained_year,
            coalesce(co.is_retained_ever, e1.is_retained_ever) as is_retained_ever,
            coalesce(co.rn_undergrad, e1.rn_undergrad) as rn_undergrad,
            coalesce(co.salesforce_id, e1.salesforce_id) as salesforce_id,
            coalesce(co.ktc_cohort, e1.ktc_cohort) as ktc_cohort,
            coalesce(co.hos, e1.hos) as hos,
            coalesce(co.advisory, e1.advisory) as advisory,
            coalesce(co.iep_status, e1.iep_status) as iep_status,
            coalesce(co.is_counseling_services, 0) as is_counseling_services,
            coalesce(co.is_student_athlete, 0) as is_student_athlete,
            coalesce(co.ada, e1.ada) as ada,
        from {{ ref("stg_powerschool__storedgrades") }} as tr
        left join
            student_roster as co
            on tr.academic_year = co.academic_year
            and tr.schoolid = co.schoolid
            and tr.studentid = co.studentid
            and {{ union_dataset_join_clause(left_alias="tr", right_alias="co") }}
        left join
            student_roster as e1
            on tr.schoolid = e1.schoolid
            and tr.studentid = e1.studentid
            and e1.year_in_school = 1
            and {{ union_dataset_join_clause(left_alias="tr", right_alias="e1") }}
        where
            tr.academic_year = {{ var("current_academic_year") }}
            and tr.storecode = 'Y1'
            and tr.is_transfer_grade
    )*/
    )

select count(*)
from
    student_roster
    /*

    students as (
        select
            _dbt_source_relation,
            academic_year,
            yearid,
            region,
            school_level,
            schoolid,
            school,
            studentid,
            student_number,
            lastfirst,
            gender,
            enroll_status,
            grade_level,
            ethnicity,
            cohort,
            year_in_school,
            advisor_name,
            is_out_of_district,
            lep_status,
            is_504,
            is_pathways,
            lunch_status,
            year_in_network,
            is_retained_year,
            is_retained_ever,
            rn_undergrad,
            salesforce_id,
            ktc_cohort,
            hos,
            advisory,
            iep_status,
            is_counseling_services,
            is_student_athlete,
            ada,
            roster_type,
            semester,
            quarter,

        from student_roster

        union all

        select
            _dbt_source_relation,
            academic_year,
            yearid,
            region,
            school_level,
            schoolid,
            school,
            studentid,
            student_number,
            lastfirst,
            gender,
            enroll_status,
            grade_level,
            ethnicity,
            cohort,
            year_in_school,
            advisor_name,
            is_out_of_district,
            lep_status,
            is_504,
            is_pathways,
            lunch_status,
            year_in_network,
            is_retained_year,
            is_retained_ever,
            rn_undergrad,
            salesforce_id,
            ktc_cohort,
            hos,
            advisory,
            iep_status,
            is_counseling_services,
            is_student_athlete,
            ada,
            roster_type,
            semester,
            quarter,

        from transfer_roster
    ),

    section_teacher as (
        select distinct
            m._dbt_source_relation,
            m.cc_yearid as yearid,
            m.cc_academic_year,
            m.cc_studentid as studentid,
            m.cc_course_number as course_number,
            m.cc_sectionid as sectionid,
            m.sections_dcid,
            m.sections_section_number as section_number,
            m.sections_external_expression as external_expression,
            m.sections_termid as termid,
            m.courses_credittype as credit_type,
            m.courses_course_name as course_name,
            m.teachernumber as teacher_number,
            m.teacher_lastfirst as teacher_name,
            m.courses_excludefromgpa as exclude_from_gpa,

            f.tutoring_nj,
            f.nj_student_tier,

            quarter,

        from {{ ref("base_powerschool__course_enrollments") }} as m
        left join
            {{ ref("int_reporting__student_filters") }} as f
            on m.cc_studentid = f.studentid
            and m.cc_academic_year = f.academic_year
            and m.courses_credittype = f.powerschool_credittype
            and {{ union_dataset_join_clause(left_alias="m", right_alias="f") }}
        cross join unnest({{ quarter }}) as quarter
        where
            not m.is_dropped_course
            and not m.is_dropped_section
            and m.rn_course_number_year = 1
            and m.cc_course_number not in ('{{ exempt_courses | join("', '") }}')
            and m.cc_academic_year = {{ var("current_academic_year") }}
    ),

    category_grades as (
        select
            _dbt_source_relation,
            yearid,
            schoolid,
            studentid,
            course_number,
            sectionid,
            is_current as is_current_quarter,
            termbin_start_date as quarter_start_date,
            termbin_end_date as quarter_end_date,
            storecode_type as category_name_code,
            storecode as category_quarter_code,
            percent_grade as category_quarter_percent_grade,
            percent_grade_y1_running as category_y1_percent_grade_running,

            if(reporting_term in ('RT1', 'RT2'), 'S1', 'S2') as semester,

            concat('Q', right(storecode, 1)) as quarter,

            avg(if(is_current, percent_grade_y1_running, null)) over (
                partition by
                    _dbt_source_relation,
                    yearid,
                    studentid,
                    course_number,
                    storecode_type
            ) as category_y1_percent_grade_current,

            round(
                avg(percent_grade) over (
                    partition by _dbt_source_relation, yearid, studentid, storecode
                ),
                2
            ) as category_quarter_average_all_courses
        from {{ ref("int_powerschool__category_grades") }}
        where
            not is_dropped_section
            and storecode_type not in ('Q', 'H')
            and termbin_start_date <= current_date('America/New_York')
            and yearid + 1990 = {{ var("current_academic_year") }}
            and course_number not in ('{{ exempt_courses | join("', '") }}')
    ),

    quarter_and_ip_y1_grades as (
        select
            _dbt_source_relation,
            yearid,
            schoolid,
            studentid,
            course_number,
            sectionid,
            termid,
            storecode as quarter,
            fg_percent as quarter_course_in_progress_percent_grade,
            fg_letter_grade as quarter_course_in_progress_letter_grade,
            fg_grade_points as quarter_course_in_progress_grade_points,
            fg_percent_adjusted as quarter_course_in_progress_percent_grade_adjusted,
            fg_letter_grade_adjusted
            as quarter_course_in_progress_letter_grade_adjusted,

            sg_percent as quarter_course_final_percent_grade,
            sg_letter_grade as quarter_course_final_letter_grade,
            sg_grade_points as quarter_course_final_grade_points,

            term_percent_grade_adjusted as quarter_course_percent_grade_that_matters,
            term_letter_grade_adjusted as quarter_course_letter_grade_that_matters,
            term_grade_points as quarter_course_grade_points_that_matters,

            need_60,
            need_70,
            need_80,
            need_90,

            y1_percent_grade as y1_course_in_progress_percent_grade,
            y1_percent_grade_adjusted as y1_course_in_progress_percent_grade_adjusted,
            y1_letter_grade as y1_course_in_progress_letter_grade,
            y1_letter_grade_adjusted as y1_course_in_progress_letter_grade_adjusted,
            y1_grade_points as y1_course_in_progress_grade_points,
            y1_grade_points_unweighted as y1_course_in_progress_grade_points_unweighted,

            nullif(citizenship, '') as quarter_citizenship,
            nullif(comment_value, '') as quarter_comment_value,

        from {{ ref("base_powerschool__final_grades") }}
        where
            not is_dropped_section
            and termbin_start_date <= current_date('America/New_York')
            and academic_year = {{ var("current_academic_year") }}
            and course_number not in ('{{ exempt_courses | join("', '") }}')

        union all

        select distinct
            _dbt_source_relation,
            yearid,
            schoolid,
            studentid,
            course_number,
            sectionid,
            termid,
            'Y1' as quarter,
            null as quarter_course_in_progress_percent_grade,
            '' as quarter_course_in_progress_letter_grade,
            null as quarter_course_in_progress_grade_points,
            null as quarter_course_in_progress_percent_grade_adjusted,
            '' as quarter_course_in_progress_letter_grade_adjusted,

            null as quarter_course_final_percent_grade,
            '' as quarter_course_final_letter_grade,
            null as quarter_course_final_grade_points,

            y1_percent_grade_adjusted as quarter_course_percent_grade_that_matters,
            y1_letter_grade_adjusted as quarter_course_letter_grade_that_matters,
            y1_grade_points as quarter_course_grade_points_that_matters,

            need_60,
            need_70,
            need_80,
            need_90,

            y1_percent_grade as y1_course_in_progress_percent_grade,
            y1_percent_grade_adjusted as y1_course_in_progress_percent_grade_adjusted,
            y1_letter_grade as y1_course_in_progress_letter_grade,
            y1_letter_grade_adjusted as y1_course_in_progress_letter_grade_adjusted,
            y1_grade_points as y1_course_in_progress_grade_points,
            y1_grade_points_unweighted as y1_course_in_progress_grade_points_unweighted,

            '' as quarter_citizenship,
            '' as quarter_comment_value,
        from {{ ref("base_powerschool__final_grades") }}
        where
            not is_dropped_section
            and termbin_is_current
            and academic_year = {{ var("current_academic_year") }}
            and course_number not in ('{{ exempt_courses | join("', '") }}')
    ),

    final_y1_historical as (
        select
            g._dbt_source_relation,
            g.academic_year,
            g.yearid,
            g.termid,
            g.schoolname,
            g.course_name,
            g.studentid,
            g.grade_level,
            g.storecode,
            g.excludefromgpa as exclude_from_gpa,
            g.percent as y1_course_final_percent_grade_adjusted,
            g.grade as y1_course_final_letter_grade_adjusted,
            g.earnedcrhrs as y1_course_final_earned_credits,
            g.potentialcrhrs as y1_course_final_potential_credit_hours,
            g.gpa_points as y1_course_final_grade_points,
            g.sectionid,

            'Q#' as quarter,
            'S#' as semester,

            if(
                g.is_transfer_grade,
                concat(
                    'T',
                    upper(regexp_extract(g._dbt_source_relation, r'(kipp\w+)_')),
                    g.dcid
                ),
                g.course_number
            ) as course_number,

            if(g.is_transfer_grade, 'Transfer', g.credit_type) as credit_type,

            if(g.is_transfer_grade, 'Transfer', g.teacher_name) as teacher_name,

        from {{ ref("stg_powerschool__storedgrades") }} as g
        where
            g.academic_year = {{ var("current_academic_year") }}
            and g.storecode = 'Y1'
            and g.is_transfer_grade
            and g.course_number not in ('{{ exempt_courses | join("', '") }}')
    ),

    gpa_analysis as (
        select
            sr._dbt_source_relation,
            sr.yearid,
            sr.studentid,

            gt.semester as gpa_semester_code,
            gt.term_name as gpa_quarter,
            gt.is_current as gpa_current_quarter,
            gt.gpa_term as gpa_for_quarter,
            gt.gpa_semester,
            gt.gpa_y1,
            gt.gpa_y1_unweighted,
            gt.total_credit_hours as gpa_total_credit_hours,
            gt.n_failing_y1 as gpa_n_failing_y1,

            gc.cumulative_y1_gpa as gpa_cumulative_y1_gpa,
            gc.cumulative_y1_gpa_unweighted as gpa_cumulative_y1_gpa_unweighted,
            gc.cumulative_y1_gpa_projected as gpa_cumulative_y1_gpa_projected,
            gc.cumulative_y1_gpa_projected_s1 as gpa_cumulative_y1_gpa_projected_s1,
            gc.cumulative_y1_gpa_projected_s1_unweighted
            as gpa_cumulative_y1_gpa_projected_s1_unweighted,
            gc.core_cumulative_y1_gpa as gpa_core_cumulative_y1_gpa,

        from {{ ref("base_powerschool__student_enrollments") }} as sr
        left join
            {{ ref("int_powerschool__gpa_term") }} as gt
            on sr.studentid = gt.studentid
            and sr.yearid = gt.yearid
            and sr.schoolid = gt.schoolid
            and {{ union_dataset_join_clause(left_alias="sr", right_alias="gt") }}
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on sr.studentid = gc.studentid
            and sr.schoolid = gc.schoolid
            and {{ union_dataset_join_clause(left_alias="sr", right_alias="gc") }}
        where
            sr.school_level in ('MS', 'HS')
            and sr.rn_year = 1
            and gt.term_name is not null
    ),

    calendar_dates as (
        select
            c.schoolid,

            rt.academic_year,
            rt.grade_band as school_level,
            rt.name as quarter,

            min(c.date_value) as cal_quarter_start_date,
            max(c.date_value) as cal_quarter_end_date,

        from `kipptaf_powerschool.stg_powerschool__calendar_day` as c
        inner join
            `kipptaf_reporting.stg_reporting__terms` as rt
            on rt.school_id = c.schoolid
            and c.date_value between rt.start_date and rt.end_date
            and left(rt.name, 1) = 'Q'
            and rt.academic_year = `functions.current_academic_year`()
        where c.membershipvalue = 1 and c.schoolid not in (0, 999999)
        group by c.schoolid, rt.academic_year, rt.grade_band, rt.name
    ),

    final_roster as (
        select
            s._dbt_source_relation,
            s.academic_year,
            s.region,
            s.school_level,
            s.schoolid,
            s.school,
            s.student_number,
            s.studentid,
            s.salesforce_id,
            s.ktc_cohort,
            s.lastfirst,
            s.gender,
            s.enroll_status,
            s.grade_level,
            s.ethnicity,
            s.cohort,
            s.year_in_school,
            s.is_out_of_district,
            s.lep_status,
            s.is_504,
            s.is_pathways,
            s.iep_status,
            s.lunch_status,
            s.is_counseling_services,
            s.is_student_athlete,
            s.year_in_network,
            s.is_retained_year,
            s.is_retained_ever,
            s.rn_undergrad,
            s.advisory,
            s.advisor_name,
            s.ada,
            s.hos,
            s.roster_type,
            s.semester,
            s.quarter,

            m.tutoring_nj,
            m.nj_student_tier,

            qy1.quarter_course_in_progress_percent_grade,
            qy1.quarter_course_in_progress_letter_grade,
            qy1.quarter_course_in_progress_grade_points,
            qy1.quarter_course_in_progress_percent_grade_adjusted,
            qy1.quarter_course_in_progress_letter_grade_adjusted,
            qy1.quarter_course_final_percent_grade,
            qy1.quarter_course_final_letter_grade,
            qy1.quarter_course_final_grade_points,
            qy1.quarter_course_percent_grade_that_matters,
            qy1.quarter_course_letter_grade_that_matters,
            qy1.quarter_course_grade_points_that_matters,

            qy1.need_60,
            qy1.need_70,
            qy1.need_80,
            qy1.need_90,
            qy1.y1_course_in_progress_percent_grade,
            qy1.y1_course_in_progress_percent_grade_adjusted,
            qy1.y1_course_in_progress_letter_grade,
            qy1.y1_course_in_progress_letter_grade_adjusted,
            qy1.y1_course_in_progress_grade_points,
            qy1.y1_course_in_progress_grade_points_unweighted,
            qy1.quarter_citizenship,
            qy1.quarter_comment_value,

            c.is_current_quarter,
            c.quarter_start_date,
            c.quarter_end_date,
            c.category_name_code,
            c.category_quarter_code,
            c.category_quarter_percent_grade,
            c.category_y1_percent_grade_running,
            c.category_y1_percent_grade_current,
            c.category_quarter_average_all_courses,

            gpa.gpa_for_quarter,
            gpa.gpa_semester,
            gpa.gpa_y1,
            gpa.gpa_y1_unweighted,
            gpa.gpa_total_credit_hours,
            gpa.gpa_n_failing_y1,
            gpa.gpa_cumulative_y1_gpa,
            gpa.gpa_cumulative_y1_gpa_unweighted,
            gpa.gpa_cumulative_y1_gpa_projected,
            gpa.gpa_cumulative_y1_gpa_projected_s1,
            gpa.gpa_cumulative_y1_gpa_projected_s1_unweighted,
            gpa.gpa_core_cumulative_y1_gpa,

            cal.cal_quarter_end_date,

            coalesce(m.course_name, y1h.course_name) as course_name,
            coalesce(m.course_number, y1h.course_number) as course_number,
            coalesce(m.sectionid, y1h.sectionid) as sectionid,
            coalesce(safe_cast(m.sections_dcid as string), 'Transfer') as sections_dcid,
            coalesce(m.section_number, 'Transfer') as section_number,
            coalesce(m.external_expression, 'Transfer') as external_expression,
            coalesce(m.credit_type, y1h.credit_type) as credit_type,
            coalesce(m.teacher_number, 'Transfer') as teacher_number,
            coalesce(m.teacher_name, y1h.teacher_name) as teacher_name,
            coalesce(m.exclude_from_gpa, y1h.exclude_from_gpa) as exclude_from_gpa,

            coalesce(
                y1h.y1_course_final_percent_grade_adjusted,
                y1h.y1_course_final_percent_grade_adjusted
            ) as y1_course_final_percent_grade_adjusted,
            coalesce(
                y1h.y1_course_final_letter_grade_adjusted,
                y1h.y1_course_final_letter_grade_adjusted
            ) as y1_course_final_letter_grade_adjusted,
            coalesce(
                y1h.y1_course_final_earned_credits, y1h.y1_course_final_earned_credits
            ) as y1_course_final_earned_credits,
            coalesce(
                y1h.y1_course_final_potential_credit_hours,
                y1h.y1_course_final_potential_credit_hours
            ) as y1_course_final_potential_credit_hours,
            coalesce(
                y1h.y1_course_final_grade_points, y1h.y1_course_final_grade_points
            ) as y1_course_final_grade_points,

            if(s.ada >= 0.80, 1, 0) as ada_above_or_at_80,

        from students as s
        left join
            section_teacher as m
            on s.yearid = m.yearid
            and s.studentid = m.studentid
            and s.quarter = m.quarter
            and {{ union_dataset_join_clause(left_alias="s", right_alias="m") }}
        left join
            final_y1_historical as y1h
            on m.yearid = y1h.yearid
            and m.studentid = y1h.studentid
            and m.course_number = y1h.course_number
            and m.sectionid = y1h.sectionid
            and m.quarter = y1h.quarter
            and y1h.credit_type != 'Transfer'
            and {{ union_dataset_join_clause(left_alias="m", right_alias="y1h") }}
        left join
            final_y1_historical as y1t
            on s.yearid = y1t.yearid
            and s.studentid = y1t.studentid
            and s.quarter = y1t.quarter
            and s.grade_level = y1t.grade_level
            and y1t.credit_type = 'Transfer'
            and {{ union_dataset_join_clause(left_alias="s", right_alias="y1t") }}
        left join
            quarter_and_ip_y1_grades as qy1
            on m.yearid = qy1.yearid
            and m.studentid = qy1.studentid
            and m.course_number = qy1.course_number
            and m.sectionid = qy1.sectionid
            and m.quarter = qy1.quarter
            and {{ union_dataset_join_clause(left_alias="m", right_alias="qy1") }}
        left join
            category_grades as c
            on m.yearid = c.yearid
            and m.studentid = c.studentid
            and m.course_number = c.course_number
            and m.sectionid = c.sectionid
            and m.quarter = c.quarter
            and {{ union_dataset_join_clause(left_alias="m", right_alias="c") }}
        left join
            gpa_analysis as gpa
            on s.yearid = gpa.yearid
            and s.studentid = gpa.studentid
            and s.quarter = gpa.gpa_quarter
            and {{ union_dataset_join_clause(left_alias="s", right_alias="gpa") }}
        left join
            calendar_dates as cal
            on s.schoolid = cal.schoolid
            and s.school_level = cal.school_level
            and s.quarter = cal.quarter
    ),

    final_roster_with_teacher_assign_data as (
        select
            f._dbt_source_relation,
            f.academic_year,
            f.region,
            f.school_level,
            f.schoolid,
            f.school,
            f.student_number,
            f.studentid,
            f.salesforce_id,
            f.ktc_cohort,
            f.lastfirst,
            f.gender,
            f.enroll_status,
            f.grade_level,
            f.ethnicity,
            f.cohort,
            f.year_in_school,
            f.is_out_of_district,
            f.lep_status,
            f.is_504,
            f.is_pathways,
            f.iep_status,
            f.lunch_status,
            f.is_counseling_services,
            f.is_student_athlete,
            f.year_in_network,
            f.is_retained_year,
            f.is_retained_ever,
            f.rn_undergrad,
            f.advisory,
            f.advisor_name,
            f.ada,
            f.ada_above_or_at_80,
            f.hos,
            f.roster_type,
            f.semester,
            f.quarter,
            f.tutoring_nj,
            f.nj_student_tier,
            f.course_name,
            f.course_number,
            f.sectionid,
            f.section_number,
            f.sections_dcid,
            f.external_expression,
            f.credit_type,
            f.teacher_number,
            f.teacher_name,
            f.exclude_from_gpa,
            f.y1_course_final_percent_grade_adjusted,
            f.y1_course_final_letter_grade_adjusted,
            f.y1_course_final_earned_credits,
            f.y1_course_final_potential_credit_hours,
            f.y1_course_final_grade_points,
            f.quarter_course_in_progress_percent_grade,
            f.quarter_course_in_progress_letter_grade,
            f.quarter_course_in_progress_grade_points,
            f.quarter_course_in_progress_percent_grade_adjusted,
            f.quarter_course_in_progress_letter_grade_adjusted,
            f.quarter_course_final_percent_grade,
            f.quarter_course_final_letter_grade,
            f.quarter_course_final_grade_points,
            f.quarter_course_percent_grade_that_matters,
            f.quarter_course_letter_grade_that_matters,
            f.quarter_course_grade_points_that_matters,
            f.need_60,
            f.need_70,
            f.need_80,
            f.need_90,
            f.y1_course_in_progress_percent_grade,
            f.y1_course_in_progress_percent_grade_adjusted,
            f.y1_course_in_progress_letter_grade,
            f.y1_course_in_progress_letter_grade_adjusted,
            f.y1_course_in_progress_grade_points,
            f.y1_course_in_progress_grade_points_unweighted,
            f.quarter_citizenship,
            f.quarter_comment_value,
            f.is_current_quarter,
            f.quarter_start_date,
            f.quarter_end_date,
            f.cal_quarter_end_date,
            f.category_name_code,
            f.category_quarter_code,
            f.category_quarter_percent_grade,
            f.category_y1_percent_grade_running,
            f.category_y1_percent_grade_current,
            f.category_quarter_average_all_courses,
            f.gpa_for_quarter,
            f.gpa_semester,
            f.gpa_y1,
            f.gpa_y1_unweighted,
            f.gpa_total_credit_hours,
            f.gpa_n_failing_y1,
            f.gpa_cumulative_y1_gpa,
            f.gpa_cumulative_y1_gpa_unweighted,
            f.gpa_cumulative_y1_gpa_projected,
            f.gpa_cumulative_y1_gpa_projected_s1,
            f.gpa_cumulative_y1_gpa_projected_s1_unweighted,
            f.gpa_core_cumulative_y1_gpa,

            t.teacher_quarter,
            t.expected_teacher_assign_category_code,
            t.expected_teacher_assign_category_name,
            t.year_week_number,
            t.quarter_week_number,
            t.audit_start_date,
            t.audit_end_date,
            t.audit_due_date,
            t.audit_category_exp_audit_week_ytd,
            t.teacher_assign_id,
            t.teacher_assign_name,
            t.teacher_assign_score_type,
            t.teacher_assign_max_score,
            t.teacher_assign_due_date,
            t.teacher_assign_count,
            t.teacher_running_total_assign_by_cat,
            t.teacher_avg_score_for_assign_per_class_section_and_assign_id,
            t.total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
            t.total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,
            t.total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
            t.total_expected_graded_assignments_by_course_cat_qt_audit_week,
            t.total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,
            t.total_expected_graded_assignments_by_course_assign_id_qt_audit_week,
            t.percent_graded_completion_by_cat_qt_audit_week_all_courses,
            t.percent_graded_completion_by_cat_qt_audit_week,
            t.percent_graded_completion_by_assign_id_qt_audit_week,

            t.qt_teacher_no_missing_assignments,
            t.qt_teacher_s_total_less_200,
            t.qt_teacher_s_total_greater_200,
            t.w_assign_max_score_not_10,
            t.f_assign_max_score_not_10,
            t.s_max_score_greater_100,
            t.w_expected_assign_count_not_met,
            t.f_expected_assign_count_not_met,
            t.s_expected_assign_count_not_met,

            if(
                f.grade_level < 9, f.section_number, f.external_expression
            ) as section_or_period,

        from final_roster as f
        left join
            {{ ref("int_powerschool__teacher_assignment_flags") }} as t
            on f.academic_year = t.academic_year
            and f.schoolid = t.schoolid
            and f.course_number = t.course_number
            and safe_cast(f.sections_dcid as numeric) = t.sections_dcid
            and f.quarter = t.teacher_quarter
            and f.category_name_code = t.expected_teacher_assign_category_code
    ),

    final_roster_with_student_assign_data as (
        select distinct
            f._dbt_source_relation,
            f.academic_year,
            f.region,
            f.school_level,
            f.schoolid,
            f.school,
            f.student_number,
            f.studentid,
            f.enroll_status,
            f.salesforce_id,
            f.ktc_cohort,
            f.lastfirst,
            f.gender,
            f.grade_level,
            f.ethnicity,
            f.cohort,
            f.year_in_school,
            f.lep_status,
            f.is_504,
            f.is_pathways,
            f.iep_status,
            f.lunch_status,
            f.is_counseling_services,
            f.is_student_athlete,
            f.year_in_network,
            f.is_retained_year,
            f.is_retained_ever,
            f.rn_undergrad,
            f.advisory,
            f.advisor_name,
            f.ada,
            f.ada_above_or_at_80,
            f.hos,
            f.roster_type,
            f.semester,
            f.quarter,
            f.tutoring_nj,
            f.nj_student_tier,
            f.course_name,
            f.course_number,
            f.sectionid,
            f.sections_dcid,
            f.section_number,
            f.external_expression,
            f.section_or_period,
            f.credit_type,
            f.teacher_number,
            f.teacher_name,
            f.exclude_from_gpa,
            f.is_current_quarter,
            f.quarter_start_date,
            f.quarter_end_date,
            f.cal_quarter_end_date,
            f.category_name_code,
            f.category_quarter_code,
            f.category_quarter_percent_grade,
            f.category_y1_percent_grade_running,
            f.category_y1_percent_grade_current,
            f.category_quarter_average_all_courses,
            f.quarter_course_in_progress_percent_grade,
            f.quarter_course_in_progress_letter_grade,
            f.quarter_course_in_progress_grade_points,
            f.quarter_course_in_progress_percent_grade_adjusted,
            f.quarter_course_in_progress_letter_grade_adjusted,
            f.quarter_course_final_percent_grade,
            f.quarter_course_final_letter_grade,
            f.quarter_course_final_grade_points,
            f.quarter_course_percent_grade_that_matters,
            f.quarter_course_letter_grade_that_matters,
            f.quarter_course_grade_points_that_matters,
            f.need_60,
            f.need_70,
            f.need_80,
            f.need_90,
            f.quarter_citizenship,
            f.quarter_comment_value,
            f.y1_course_in_progress_percent_grade,
            f.y1_course_in_progress_percent_grade_adjusted,
            f.y1_course_in_progress_letter_grade,
            f.y1_course_in_progress_letter_grade_adjusted,
            f.y1_course_in_progress_grade_points,
            f.y1_course_in_progress_grade_points_unweighted,
            f.y1_course_final_percent_grade_adjusted,
            f.y1_course_final_letter_grade_adjusted,
            f.y1_course_final_earned_credits,
            f.y1_course_final_potential_credit_hours,
            f.y1_course_final_grade_points,
            f.gpa_for_quarter,
            f.gpa_semester,
            f.gpa_y1,
            f.gpa_y1_unweighted,
            f.gpa_total_credit_hours,
            f.gpa_n_failing_y1,
            f.gpa_cumulative_y1_gpa,
            f.gpa_cumulative_y1_gpa_unweighted,
            f.gpa_cumulative_y1_gpa_projected,
            f.gpa_cumulative_y1_gpa_projected_s1,
            f.gpa_cumulative_y1_gpa_projected_s1_unweighted,
            f.gpa_core_cumulative_y1_gpa,
            f.teacher_quarter,
            f.expected_teacher_assign_category_code,
            f.expected_teacher_assign_category_name,
            f.year_week_number,
            f.quarter_week_number,
            f.audit_start_date,
            f.audit_end_date,
            f.audit_due_date,
            f.audit_category_exp_audit_week_ytd,
            f.teacher_assign_id,
            f.teacher_assign_name,
            f.teacher_assign_score_type,
            f.teacher_assign_max_score,
            f.teacher_assign_due_date,
            f.teacher_assign_count,
            f.teacher_running_total_assign_by_cat,
            f.teacher_avg_score_for_assign_per_class_section_and_assign_id,
            f.total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
            f.total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,
            f.total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
            f.total_expected_graded_assignments_by_course_cat_qt_audit_week,
            f.total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,
            f.total_expected_graded_assignments_by_course_assign_id_qt_audit_week,
            f.percent_graded_completion_by_cat_qt_audit_week_all_courses,
            f.percent_graded_completion_by_cat_qt_audit_week,
            f.percent_graded_completion_by_assign_id_qt_audit_week,
            f.qt_teacher_no_missing_assignments,
            f.qt_teacher_s_total_less_200,
            f.qt_teacher_s_total_greater_200,
            f.w_assign_max_score_not_10,
            f.f_assign_max_score_not_10,
            f.s_max_score_greater_100,
            f.w_expected_assign_count_not_met,
            f.f_expected_assign_count_not_met,
            f.s_expected_assign_count_not_met,

            s.student_course_entry_date,
            s.assign_category_code,
            s.assign_category,
            s.assign_category_quarter,
            s.assign_id,
            s.assign_name,
            s.assign_due_date,
            s.assign_score_type,
            s.assign_score_raw,
            s.assign_score_converted,
            s.assign_max_score,
            s.assign_is_exempt,
            s.assign_is_late,
            s.assign_is_missing,

            s.assign_null_score,
            s.assign_score_above_max,
            s.assign_exempt_with_score,
            s.assign_w_score_less_5,
            s.assign_f_score_less_5,
            s.assign_w_missing_score_not_5,
            s.assign_f_missing_score_not_5,
            s.assign_s_score_less_50p,
            s.assign_s_ms_score_not_conversion_chart_options,
            s.assign_s_hs_score_not_conversion_chart_options,

            if(
                sum(
                    if(
                        assign_id is null
                        and student_course_entry_date >= teacher_assign_due_date - 7
                        and quarter != 'Y1'
                        and concat(region, school_level)
                        not in ('CamdenES', 'NewarkES'),
                        0,
                        1
                    )
                ) over (
                    partition by
                        quarter, student_number, course_number, section_or_period
                )
                = 0,
                1,
                0
            ) as qt_assign_no_course_assignments,

            if(
                region = 'Miami'
                and current_date('America/New_York')
                between cal_quarter_end_date and (cal_quarter_end_date + 14)
                and grade_level = 0
                and course_name = 'HR'
                and quarter != 'Y1'
                and quarter_citizenship is null,
                1,
                0
            ) as qt_kg_conduct_code_missing,

            if(
                region = 'Miami'
                and current_date('America/New_York')
                between cal_quarter_end_date and (cal_quarter_end_date + 14)
                and grade_level = 0
                and course_name != 'HR'
                and quarter != 'Y1'
                and quarter_citizenship is not null,
                1,
                0
            ) as qt_kg_conduct_code_not_hr,

            if(
                region = 'Miami'
                and current_date('America/New_York')
                between cal_quarter_end_date and (cal_quarter_end_date + 14)
                and grade_level != 0
                and course_name != 'HR'
                and quarter != 'Y1'
                and quarter_citizenship is null,
                1,
                0
            ) as qt_g1_g8_conduct_code_missing,

            if(
                region = 'Miami'
                and current_date('America/New_York')
                between cal_quarter_end_date and (cal_quarter_end_date + 14)
                and grade_level = 0
                and course_name = 'HR'
                and quarter != 'Y1'
                and quarter_citizenship is not null
                and quarter_citizenship not in ('E', 'G', 'S', 'M'),
                1,
                0
            ) as qt_kg_conduct_code_incorrect,

            if(
                region = 'Miami'
                and current_date('America/New_York')
                between cal_quarter_end_date and (cal_quarter_end_date + 14)
                and grade_level != 0
                and course_name != 'HR'
                and quarter != 'Y1'
                and quarter_citizenship is not null
                and quarter_citizenship not in ('A', 'B', 'C', 'D', 'E', 'F'),
                1,
                0
            ) as qt_g1_g8_conduct_code_incorrect,

            if(
                region != 'Miami'
                and current_date('America/New_York')
                between cal_quarter_end_date and (cal_quarter_end_date + 14)
                and grade_level > 4
                and quarter != 'Y1'
                and quarter_course_percent_grade_that_matters < 70
                and quarter_comment_value is null,
                1,
                0
            ) as qt_grade_70_comment_missing,

            if(
                region != 'Miami'
                and current_date('America/New_York')
                between cal_quarter_end_date and (cal_quarter_end_date + 14)
                and grade_level < 5
                and quarter != 'Y1'
                and (course_name = 'HR' or credit_type in ('MATH', 'ENG'))
                and quarter_comment_value is null,
                1,
                0
            ) as qt_es_comment_missing,

            if(
                region = 'Miami'
                and current_date('America/New_York')
                between cal_quarter_end_date and (cal_quarter_end_date + 14)
                and quarter != 'Y1'
                and quarter_comment_value is null,
                1,
                0
            ) as qt_comment_missing,

            if(
                quarter != 'Y1' and quarter_course_percent_grade_that_matters > 100,
                1,
                0
            ) as qt_percent_grade_greater_100,

            if(
                quarter != 'Y1'
                and grade_level < 5
                and category_name_code = 'W'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                1,
                0
            ) as w_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                quarter != 'Y1'
                and category_name_code = 'F'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                1,
                0
            ) as f_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                quarter != 'Y1'
                and category_name_code = 'S'
                and percent_graded_completion_by_cat_qt_audit_week != 1,
                1,
                0
            ) as s_percent_graded_completion_by_qt_audit_week_not_100,

            if(
                quarter != 'Y1'
                and grade_level > 4
                and ada_above_or_at_80 = 1
                and quarter_course_grade_points_that_matters < 2.0,
                1,
                0
            ) as qt_student_is_ada_80_plus_gpa_less_2,

            if(
                quarter != 'Y1'
                and grade_level > 4
                and category_name_code = 'W'
                and abs(
                    round(category_quarter_average_all_courses, 2)
                    - round(category_quarter_percent_grade, 2)
                )
                >= 30,
                1,
                0
            ) as w_grade_inflation,

            if(
                region = 'Miami'
                and quarter != 'Y!'
                and category_name_code = 'W'
                and category_quarter_percent_grade is null,
                1,
                0
            ) as qt_effort_grade_missing,

        from final_roster_with_teacher_assign_data as f
        left join
            {{ ref("int_powerschool__student_assignment_flags") }} as s
            on f.academic_year = s.academic_year
            and f.student_number = s.student_number
            and f.course_number = s.course_number
            and safe_cast(f.sections_dcid as numeric) = s.sections_dcid
            and f.quarter = s.assign_quarter
            and f.category_name_code = s.assign_category_code
            and f.quarter_week_number = s.quarter_week_number
            and f.teacher_assign_id = s.assign_id
    )

select distinct
    _dbt_source_relation,
    academic_year,
    region,
    school_level,
    schoolid,
    school,
    student_number,
    studentid,
    enroll_status,
    salesforce_id,
    ktc_cohort,
    lastfirst,
    gender,
    grade_level,
    ethnicity,
    cohort,
    year_in_school,
    lep_status,
    is_504,
    is_pathways,
    iep_status,
    lunch_status,
    is_counseling_services,
    is_student_athlete,
    year_in_network,
    is_retained_year,
    is_retained_ever,
    rn_undergrad,
    advisory,
    advisor_name,
    ada,
    ada_above_or_at_80,
    hos,
    roster_type,
    semester,
    quarter,
    tutoring_nj,
    nj_student_tier,
    course_name,
    course_number,
    sectionid,
    sections_dcid,
    section_number,
    external_expression,
    credit_type,
    teacher_number,
    teacher_name,
    exclude_from_gpa,
    is_current_quarter,
    quarter_start_date,
    quarter_end_date,
    category_name_code,
    category_quarter_code,
    category_quarter_percent_grade,
    category_y1_percent_grade_running,
    category_y1_percent_grade_current,
    category_quarter_average_all_courses,
    quarter_course_in_progress_percent_grade,
    quarter_course_in_progress_letter_grade,
    quarter_course_in_progress_grade_points,
    quarter_course_in_progress_percent_grade_adjusted,
    quarter_course_in_progress_letter_grade_adjusted,
    quarter_course_final_percent_grade,
    quarter_course_final_letter_grade,
    quarter_course_final_grade_points,
    quarter_course_percent_grade_that_matters,
    quarter_course_letter_grade_that_matters,
    quarter_course_grade_points_that_matters,
    need_60,
    need_70,
    need_80,
    need_90,
    quarter_citizenship,
    quarter_comment_value,
    y1_course_in_progress_percent_grade,
    y1_course_in_progress_percent_grade_adjusted,
    y1_course_in_progress_letter_grade,
    y1_course_in_progress_letter_grade_adjusted,
    y1_course_in_progress_grade_points,
    y1_course_in_progress_grade_points_unweighted,
    y1_course_final_percent_grade_adjusted,
    y1_course_final_letter_grade_adjusted,
    y1_course_final_earned_credits,
    y1_course_final_potential_credit_hours,
    y1_course_final_grade_points,
    gpa_for_quarter,
    gpa_semester,
    gpa_y1,
    gpa_y1_unweighted,
    gpa_total_credit_hours,
    gpa_n_failing_y1,
    gpa_cumulative_y1_gpa,
    gpa_cumulative_y1_gpa_unweighted,
    gpa_cumulative_y1_gpa_projected,
    gpa_cumulative_y1_gpa_projected_s1,
    gpa_cumulative_y1_gpa_projected_s1_unweighted,
    gpa_core_cumulative_y1_gpa,
    teacher_quarter,
    expected_teacher_assign_category_code,
    expected_teacher_assign_category_name,
    year_week_number,
    quarter_week_number,
    audit_start_date,
    audit_end_date,
    audit_due_date,
    audit_category_exp_audit_week_ytd,
    teacher_assign_id,
    teacher_assign_name,
    teacher_assign_score_type,
    teacher_assign_max_score,
    teacher_assign_due_date,
    teacher_assign_count,
    teacher_running_total_assign_by_cat,
    teacher_avg_score_for_assign_per_class_section_and_assign_id,
    total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
    total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,
    total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
    total_expected_graded_assignments_by_course_cat_qt_audit_week,
    total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,
    total_expected_graded_assignments_by_course_assign_id_qt_audit_week,
    percent_graded_completion_by_cat_qt_audit_week_all_courses,
    percent_graded_completion_by_cat_qt_audit_week,
    percent_graded_completion_by_assign_id_qt_audit_week,
    student_course_entry_date,
    assign_category_code,
    assign_category,
    assign_category_quarter,
    assign_id,
    assign_name,
    assign_due_date,
    assign_score_type,
    assign_score_raw,
    assign_score_converted,
    assign_max_score,
    assign_is_exempt,
    assign_is_late,
    assign_is_missing,

    audit_flag_name,
    audit_flag_value,

from
    final_roster_with_final_combo_calcs unpivot (
        audit_flag_value for audit_flag_name in (
            qt_teacher_no_missing_assignments,
            qt_teacher_s_total_less_200,
            qt_teacher_s_total_greater_200,
            w_assign_max_score_not_10,
            f_assign_max_score_not_10,
            s_max_score_greater_100,
            w_expected_assign_count_not_met,
            f_expected_assign_count_not_met,
            s_expected_assign_count_not_met,
            assign_null_score,
            assign_score_above_max,
            assign_exempt_with_score,
            assign_w_score_less_5,
            assign_f_score_less_5,
            assign_w_missing_score_not_5,
            assign_f_missing_score_not_5,
            assign_s_score_less_50p,
            qt_assign_no_course_assignments,
            qt_kg_conduct_code_missing,
            qt_kg_conduct_code_not_hr,
            qt_g1_g8_conduct_code_missing,
            qt_kg_conduct_code_incorrect,
            qt_g1_g8_conduct_code_incorrect,
            qt_grade_70_comment_missing,
            qt_es_comment_missing,
            qt_comment_missing,
            qt_percent_grade_greater_100,
            w_percent_graded_completion_by_qt_audit_week_not_100,
            f_percent_graded_completion_by_qt_audit_week_not_100,
            s_percent_graded_completion_by_qt_audit_week_not_100,
            qt_student_is_ada_80_plus_gpa_less_2,
            w_grade_inflation
        )
    )
where audit_flag_value = 1

union all

select distinct
    _dbt_source_relation,
    academic_year,
    region,
    school_level,
    schoolid,
    school,
    student_number,
    studentid,
    enroll_status,
    salesforce_id,
    ktc_cohort,
    lastfirst,
    gender,
    grade_level,
    ethnicity,
    cohort,
    year_in_school,
    lep_status,
    is_504,
    is_pathways,
    iep_status,
    lunch_status,
    is_counseling_services,
    is_student_athlete,
    year_in_network,
    is_retained_year,
    is_retained_ever,
    rn_undergrad,
    advisory,
    advisor_name,
    ada,
    ada_above_or_at_80,
    hos,
    roster_type,
    semester,
    quarter,
    tutoring_nj,
    nj_student_tier,
    course_name,
    course_number,
    sectionid,
    sections_dcid,
    section_number,
    external_expression,
    credit_type,
    teacher_number,
    teacher_name,
    tableau_username,
    exclude_from_gpa,
    is_current_quarter,
    quarter_start_date,
    quarter_end_date,
    category_name_code,
    category_quarter_code,
    category_quarter_percent_grade,
    category_y1_percent_grade_running,
    category_y1_percent_grade_current,
    category_quarter_average_all_courses,
    quarter_course_in_progress_percent_grade,
    quarter_course_in_progress_letter_grade,
    quarter_course_in_progress_grade_points,
    quarter_course_in_progress_percent_grade_adjusted,
    quarter_course_in_progress_letter_grade_adjusted,
    quarter_course_final_percent_grade,
    quarter_course_final_letter_grade,
    quarter_course_final_grade_points,
    quarter_course_percent_grade_that_matters,
    quarter_course_letter_grade_that_matters,
    quarter_course_grade_points_that_matters,
    need_60,
    need_70,
    need_80,
    need_90,
    quarter_citizenship,
    quarter_comment_value,
    y1_course_in_progress_percent_grade,
    y1_course_in_progress_percent_grade_adjusted,
    y1_course_in_progress_letter_grade,
    y1_course_in_progress_letter_grade_adjusted,
    y1_course_in_progress_grade_points,
    y1_course_in_progress_grade_points_unweighted,
    y1_course_final_percent_grade_adjusted,
    y1_course_final_letter_grade_adjusted,
    y1_course_final_earned_credits,
    y1_course_final_potential_credit_hours,
    y1_course_final_grade_points,
    gpa_for_quarter,
    gpa_semester,
    gpa_y1,
    gpa_y1_unweighted,
    gpa_total_credit_hours,
    gpa_n_failing_y1,
    gpa_cumulative_y1_gpa,
    gpa_cumulative_y1_gpa_unweighted,
    gpa_cumulative_y1_gpa_projected,
    gpa_cumulative_y1_gpa_projected_s1,
    gpa_cumulative_y1_gpa_projected_s1_unweighted,
    gpa_core_cumulative_y1_gpa,
    teacher_quarter,
    expected_teacher_assign_category_code,
    expected_teacher_assign_category_name,
    year_week_number,
    quarter_week_number,
    audit_start_date,
    audit_end_date,
    audit_due_date,
    audit_category_exp_audit_week_ytd,
    teacher_assign_id,
    teacher_assign_name,
    teacher_assign_score_type,
    teacher_assign_max_score,
    teacher_assign_due_date,
    teacher_assign_count,
    teacher_running_total_assign_by_cat,
    teacher_avg_score_for_assign_per_class_section_and_assign_id,
    total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
    total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,
    total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
    total_expected_graded_assignments_by_course_cat_qt_audit_week,
    total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,
    total_expected_graded_assignments_by_course_assign_id_qt_audit_week,
    percent_graded_completion_by_cat_qt_audit_week_all_courses,
    percent_graded_completion_by_cat_qt_audit_week,
    percent_graded_completion_by_assign_id_qt_audit_week,
    student_course_entry_date,
    assign_category_code,
    assign_category,
    assign_category_quarter,
    assign_id,
    assign_name,
    assign_due_date,
    assign_score_type,
    assign_score_raw,
    assign_score_converted,
    assign_max_score,
    assign_is_exempt,
    assign_is_late,
    assign_is_missing,

    'No Issues' as audit_flag_name,
    null as audit_flag_value,

from
    final_roster_with_final_combo_calcs unpivot (
        audit_flag_value for audit_flag_name in (
            qt_teacher_no_missing_assignments,
            qt_teacher_s_total_less_200,
            qt_teacher_s_total_greater_200,
            w_assign_max_score_not_10,
            f_assign_max_score_not_10,
            s_max_score_greater_100,
            w_expected_assign_count_not_met,
            f_expected_assign_count_not_met,
            s_expected_assign_count_not_met,
            assign_null_score,
            assign_score_above_max,
            assign_exempt_with_score,
            assign_w_score_less_5,
            assign_f_score_less_5,
            assign_w_missing_score_not_5,
            assign_f_missing_score_not_5,
            assign_s_score_less_50p,
            qt_assign_no_course_assignments,
            qt_kg_conduct_code_missing,
            qt_kg_conduct_code_not_hr,
            qt_g1_g8_conduct_code_missing,
            qt_kg_conduct_code_incorrect,
            qt_g1_g8_conduct_code_incorrect,
            qt_grade_70_comment_missing,
            qt_es_comment_missing,
            qt_comment_missing,
            qt_percent_grade_greater_100,
            w_percent_graded_completion_by_qt_audit_week_not_100,
            f_percent_graded_completion_by_qt_audit_week_not_100,
            s_percent_graded_completion_by_qt_audit_week_not_100,
            qt_student_is_ada_80_plus_gpa_less_2,
            w_grade_inflation
        )
    )
where audit_flag_value = 0*/
    
