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
    ),

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
    ),

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
            m.cc_academic_year = {{ var("current_academic_year") }}
            and not m.is_dropped_course
            and not m.is_dropped_section
            and m.rn_course_number_year = 1
            and m.cc_course_number not in ('{{ exempt_courses | join("', '") }}')
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
            rt.is_current as is_current_quarter,

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
        group by c.schoolid, rt.academic_year, rt.grade_band, rt.name, rt.is_current
    ),

    final_roster as (
        /*select
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
        where concat(s.school_level, s.region) not in ('ESCamden', 'ESNewark')

        union all
*/
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

            cal.is_current_quarter,
            cal.cal_quarter_start_date as quarter_start_date,
            cal.cal_quarter_end_date as quarter_end_date,
            '' as category_name_code,
            '' as category_quarter_code,
            null as category_quarter_percent_grade,
            null as category_y1_percent_grade_running,
            null as category_y1_percent_grade_current,
            null as category_quarter_average_all_courses,

            null as gpa_for_quarter,
            null as gpa_semester,
            null as gpa_y1,
            null as gpa_y1_unweighted,
            null as gpa_total_credit_hours,
            null as gpa_n_failing_y1,
            null as gpa_cumulative_y1_gpa,
            null as gpa_cumulative_y1_gpa_unweighted,
            null as gpa_cumulative_y1_gpa_projected,
            null as gpa_cumulative_y1_gpa_projected_s1,
            null as gpa_cumulative_y1_gpa_projected_s1_unweighted,
            null as gpa_core_cumulative_y1_gpa,

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

            null as y1_course_final_percent_grade_adjusted,
            null as y1_course_final_letter_grade_adjusted,
            '' as y1_course_final_earned_credits,
            '' as y1_course_final_potential_credit_hours,
            '' as y1_course_final_grade_points,
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
            calendar_dates as cal
            on s.schoolid = cal.schoolid
            and s.school_level = cal.school_level
            and s.quarter = cal.quarter
        where concat(s.school_level, s.region) in ('ESCamden', 'ESNewark')
    )

select *
from final_roster
