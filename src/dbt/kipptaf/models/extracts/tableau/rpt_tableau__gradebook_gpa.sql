{%- set term = ["Q1", "Q2", "Q3", "Q4", "Y1"] -%}
{%- set exempt_courses = [
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
] -%}

with
    student_roster as (
        select
            enr._dbt_source_relation,
            enr.academic_year,
            enr.yearid,
            enr.region,
            enr.school_level,
            enr.schoolid,
            enr.school_abbreviation,  -- as school,
            enr.studentid,
            enr.student_number,
            enr.lastfirst,
            enr.gender,
            enr.enroll_status,
            enr.grade_level,
            enr.ethnicity,
            enr.cohort,
            enr.year_in_school,
            enr.advisor_lastfirst,  -- as advisor_name,
            enr.is_out_of_district,
            enr.lep_status,
            enr.is_504,
            enr.is_self_contained,  -- as is_pathways,
            enr.lunch_status,
            enr.year_in_network,
            enr.is_retained_year,
            enr.is_retained_ever,
            enr.rn_undergrad,

            term,

            ktc.contact_id as salesforce_id,
            ktc.ktc_cohort,

            hos.head_of_school_preferred_name_lastfirst as head_of_school,  -- hos

            'Local' as roster_type,

            if(
                enr.school_level in ('ES', 'MS'),
                enr.advisory_name,
                enr.advisor_lastfirst
            ) as advisory,
            if(enr.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

            case
                when term in ('Q1', 'Q2')
                then 'S1'
                when term in ('Q3', 'Q4')
                then 'S2'
                else 'S#'  /* for Y1 */
            end as semester,

            if(sp.studentid is not null, 1, null) as is_counseling_services,

            if(sa.studentid is not null, 1, null) as is_student_athlete,

            round(ada.ada, 3) as ada,
        from {{ ref("base_powerschool__student_enrollments") }} as enr
        cross join unnest({{ term }}) as term
        left join
            {{ ref("int_kippadb__roster") }} as ktc
            on enr.student_number = ktc.student_number
        left join
            {{ ref("int_people__leadership_crosswalk") }} as hos
            on enr.schoolid = hos.home_work_location_powerschool_school_id
        left join
            {{ ref("int_powerschool__spenrollments") }} as sp
            on enr.studentid = sp.studentid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="sp") }}
            and current_date('{{ var("local_timezone") }}')
            between sp.enter_date and sp.exit_date
            and sp.specprog_name = 'Counseling Services'
        left join
            {{ ref("int_powerschool__spenrollments") }} as sa
            on enr.studentid = sa.studentid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="sa") }}
            and current_date('{{ var("local_timezone") }}')
            between sa.enter_date and sa.exit_date
            and sa.specprog_name = 'Student Athlete'
        left join
            {{ ref("int_powerschool__ada") }} as ada
            on enr.studentid = ada.studentid
            and enr.yearid = ada.yearid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="ada") }}
        where
            enr.academic_year = {{ var("current_academic_year") }}
            and enr.rn_year = 1
            and not enr.is_out_of_district
            and enr.grade_level != 99
    ),

    y1_historical as (
        select
            tr._dbt_source_relation,
            tr.studentid,
            tr.academic_year,
            tr.yearid,
            tr.schoolname,
            tr.grade_level,
            tr.course_name,
            tr.sectionid,
            tr.storecode,
            tr.termid,
            tr.percent as y1_course_final_percent_grade_adjusted,
            tr.grade as y1_course_final_letter_grade_adjusted,
            tr.earnedcrhrs as y1_course_final_earned_credits,
            tr.potentialcrhrs as y1_course_final_potential_credit_hours,
            tr.gpa_points as y1_course_final_grade_points,
            tr.excludefromgpa as exclude_from_gpa,
            tr.is_transfer_grade,

            'Q#' as term,
            'S#' as semester,

            if(tr.is_transfer_grade, 'Transfer', tr.credit_type) as credit_type,
            if(tr.is_transfer_grade, 'Transfer', tr.teacher_name) as teacher_name,
            if(tr.is_transfer_grade, 'Transfer', 'Local') as roster_type,
            if(
                tr.is_transfer_grade,
                concat(
                    'T',
                    upper(regexp_extract(tr._dbt_source_relation, r'(kipp\w+)_')),
                    tr.dcid
                ),
                tr.course_number
            ) as course_number,

            coalesce(co.student_number, e1.student_number) as student_number,
            coalesce(co.salesforce_id, e1.salesforce_id) as salesforce_id,
            coalesce(co.lastfirst, e1.lastfirst) as lastfirst,
            coalesce(co.enroll_status, e1.enroll_status) as enroll_status,
            coalesce(co.cohort, e1.cohort) as cohort,
            coalesce(co.ktc_cohort, e1.ktc_cohort) as ktc_cohort,
            coalesce(co.gender, e1.gender) as gender,
            coalesce(co.ethnicity, e1.ethnicity) as ethnicity,
            coalesce(co.region, e1.region) as region,
            coalesce(co.school_level, e1.school_level) as school_level,
            coalesce(co.schoolid, e1.schoolid) as schoolid,
            coalesce(co.school, e1.school) as school,
            coalesce(co.advisory, e1.advisory) as advisory,
            coalesce(co.hos, e1.hos) as hos,
            coalesce(co.year_in_school, e1.year_in_school) as year_in_school,
            coalesce(co.year_in_network, e1.year_in_network) as year_in_network,
            coalesce(co.rn_undergrad, e1.rn_undergrad) as rn_undergrad,
            coalesce(co.advisor_name, e1.advisor_name) as advisor_name,
            coalesce(co.lunch_status, e1.lunch_status) as lunch_status,
            coalesce(co.iep_status, e1.iep_status) as iep_status,
            coalesce(co.lep_status, e1.lep_status) as lep_status,
            coalesce(co.is_504, e1.is_504) as is_504,
            coalesce(co.is_pathways, e1.is_pathways) as is_pathways,
            coalesce(
                co.is_out_of_district, e1.is_out_of_district
            ) as is_out_of_district,
            coalesce(co.is_retained_year, e1.is_retained_year) as is_retained_year,
            coalesce(co.is_retained_ever, e1.is_retained_ever) as is_retained_ever,
            coalesce(co.is_counseling_services, 0) as is_counseling_services,
            coalesce(co.is_student_athlete, 0) as is_student_athlete,
            coalesce(co.ada, e1.ada) as ada,
        from {{ ref("stg_powerschool__storedgrades") }} as tr
        left join
            student_roster as co
            on tr.studentid = co.studentid
            and tr.academic_year = co.academic_year
            and tr.schoolid = co.schoolid
            and {{ union_dataset_join_clause(left_alias="tr", right_alias="co") }}
        left join
            student_roster as e1
            on tr.studentid = e1.studentid
            and tr.schoolid = e1.schoolid
            and {{ union_dataset_join_clause(left_alias="tr", right_alias="e1") }}
            and e1.year_in_school = 1
        where
            tr.academic_year = {{ var("current_academic_year") }}
            and tr.storecode = 'Y1'
            and tr.course_number not in ('{{ exempt_courses | join("', '") }}')
    ),

    section_teacher as (
        select
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
            m.teacher_lastfirst,  -- as teacher_name,
            m.courses_excludefromgpa as exclude_from_gpa,

            f.tutoring_nj,
            f.nj_student_tier,
        from {{ ref("base_powerschool__course_enrollments") }} as m
        left join
            {{ ref("int_reporting__student_filters") }} as f
            on m.cc_studentid = f.studentid
            and m.cc_academic_year = f.academic_year
            and m.courses_credittype = f.powerschool_credittype
            and {{ union_dataset_join_clause(left_alias="m", right_alias="f") }}
        where
            m.cc_academic_year = {{ var("current_academic_year") }}
            and m.rn_course_number_year = 1
            and not m.is_dropped_section
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

            concat('Q', storecode_order) as term,

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
            yearid = {{ var("current_academic_year") }} - 1990
            and not is_dropped_section
            and storecode_type not in ('Q', 'H')
            and course_number not in ('{{ exempt_courses | join("', '") }}')
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')
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
            storecode as term,
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
            citizenship as quarter_citizenship,
            comment_value as quarter_comment_value,
        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and course_number not in ('{{ exempt_courses | join("', '") }}')
            and not is_dropped_section
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')

        union all

        select
            _dbt_source_relation,
            yearid,
            schoolid,
            studentid,
            course_number,
            sectionid,
            termid,

            'Y1' as term,

            null as quarter_course_in_progress_percent_grade,
            null as quarter_course_in_progress_letter_grade,
            null as quarter_course_in_progress_grade_points,
            null as quarter_course_in_progress_percent_grade_adjusted,
            null as quarter_course_in_progress_letter_grade_adjusted,
            null as quarter_course_final_percent_grade,
            null as quarter_course_final_letter_grade,
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

            null as quarter_citizenship,
            null as quarter_comment_value,
        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and termbin_is_current
            and not is_dropped_section
            and course_number not in ('{{ exempt_courses | join("', '") }}')
    ),

    gpa_analysis as (
        select
            gt._dbt_source_relation,
            gt.studentid,
            gt.yearid,
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
        from {{ ref("int_powerschool__gpa_term") }} as gt
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on gt.studentid = gc.studentid
            and gt.schoolid = gc.schoolid
            and {{ union_dataset_join_clause(left_alias="gt", right_alias="gc") }}
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
            s.term,

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
            coalesce(m.sections_dcid, 'Transfer') as sections_dcid,
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

            if(
                s.grade_level < 9, s.section_number, s.external_expression
            ) as section_or_period,
        from students as s
        left join
            section_teacher as m
            on s.yearid = m.yearid
            and s.studentid = m.studentid
            and s.term = m.term
            and {{ union_dataset_join_clause(left_alias="s", right_alias="m") }}
        left join
            final_y1_historical as y1h
            on m.yearid = y1h.yearid
            and m.studentid = y1h.studentid
            and m.course_number = y1h.course_number
            and m.sectionid = y1h.sectionid
            and m.term = y1h.term
            and y1h.credit_type != 'Transfer'
            and {{ union_dataset_join_clause(left_alias="m", right_alias="y1h") }}
        left join
            final_y1_historical as y1t
            on s.yearid = y1t.yearid
            and s.studentid = y1t.studentid
            and s.term = y1t.term
            and s.grade_level = y1t.grade_level
            and y1t.credit_type = 'Transfer'
            and {{ union_dataset_join_clause(left_alias="s", right_alias="y1t") }}
        left join
            quarter_and_ip_y1_grades as qy1
            on m.yearid = qy1.yearid
            and m.studentid = qy1.studentid
            and m.course_number = qy1.course_number
            and m.sectionid = qy1.sectionid
            and m.term = qy1.term
            and {{ union_dataset_join_clause(left_alias="m", right_alias="qy1") }}
        left join
            category_grades as c
            on m.yearid = c.yearid
            and m.studentid = c.studentid
            and m.course_number = c.course_number
            and m.sectionid = c.sectionid
            and m.term = c.term
            and {{ union_dataset_join_clause(left_alias="m", right_alias="c") }}
        left join
            gpa_analysis as gpa
            on s.yearid = gpa.yearid
            and s.studentid = gpa.studentid
            and s.term = gpa.gpa_quarter
            and {{ union_dataset_join_clause(left_alias="s", right_alias="gpa") }}
        where concat(s.school_level, s.region) not in ('ESCamden', 'ESNewark')

        union all

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
            s.term,

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
            null as category_name_code,
            null as category_quarter_code,
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
            coalesce(m.sections_dcid, 'Transfer') as sections_dcid,
            coalesce(m.section_number, 'Transfer') as section_number,
            coalesce(m.external_expression, 'Transfer') as external_expression,
            coalesce(m.credit_type, y1h.credit_type) as credit_type,
            coalesce(m.teacher_number, 'Transfer') as teacher_number,
            coalesce(m.teacher_name, y1h.teacher_name) as teacher_name,
            coalesce(m.exclude_from_gpa, y1h.exclude_from_gpa) as exclude_from_gpa,

            null as y1_course_final_percent_grade_adjusted,
            null as y1_course_final_letter_grade_adjusted,
            null as y1_course_final_earned_credits,
            null as y1_course_final_potential_credit_hours,
            null as y1_course_final_grade_points,

            if(s.ada >= 0.80, 1, 0) as ada_above_or_at_80,

            if(
                s.grade_level < 9, s.section_number, s.external_expression
            ) as section_or_period,
        from students as s
        left join
            section_teacher as m
            on s.yearid = m.yearid
            and s.studentid = m.studentid
            and s.term = m.term
            and {{ union_dataset_join_clause(left_alias="s", right_alias="m") }}
        left join
            final_y1_historical as y1h
            on m.yearid = y1h.yearid
            and m.studentid = y1h.studentid
            and m.course_number = y1h.course_number
            and m.sectionid = y1h.sectionid
            and m.term = y1h.term
            and y1h.credit_type != 'Transfer'
            and {{ union_dataset_join_clause(left_alias="m", right_alias="y1h") }}
        left join
            final_y1_historical as y1t
            on s.yearid = y1t.yearid
            and s.studentid = y1t.studentid
            and s.term = y1t.term
            and s.grade_level = y1t.grade_level
            and y1t.credit_type = 'Transfer'
            and {{ union_dataset_join_clause(left_alias="s", right_alias="y1t") }}
        left join
            quarter_and_ip_y1_grades as qy1
            on m.yearid = qy1.yearid
            and m.studentid = qy1.studentid
            and m.course_number = qy1.course_number
            and m.sectionid = qy1.sectionid
            and m.term = qy1.term
            and {{ union_dataset_join_clause(left_alias="m", right_alias="qy1") }}
        where concat(s.school_level, s.region) in ('ESCamden', 'ESNewark')
    )

select
    _dbt_source_relation,
    roster_type,
    studentid,
    student_number,
    salesforce_id,
    lastfirst,
    enroll_status,
    cohort,
    ktc_cohort,
    gender,
    ethnicity,

    academic_year,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    advisory,
    advisor_name,
    hos,
    year_in_school,
    year_in_network,
    rn_undergrad,
    is_retained_year,
    is_retained_ever,

    lunch_status,
    iep_status,
    lep_status,
    is_504,
    is_pathways,
    is_counseling_services,
    is_student_athlete,
    tutoring_nj,
    nj_student_tier,

    ada,
    ada_above_or_at_80,

    `quarter`,
    semester,
    quarter_start_date,
    quarter_end_date,
    is_current_quarter,

    credit_type,
    course_number,
    course_name,
    exclude_from_gpa,
    sectionid,
    sections_dcid,
    section_number,
    external_expression,
    teacher_number,
    teacher_name,

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
from final_roster
