with
    term as (
        select
            _dbt_source_relation,
            schoolid,
            yearid,
            storecode,
            date1 as term_start_date,
            date2 as term_end_date,

            if(
                current_date('{{ var("local_timezone") }}') between date1 and date2,
                true,
                false
            ) as is_current_term,

            case
                when storecode in ('Q1', 'Q2')
                then 'S1'
                when storecode in ('Q3', 'Q4')
                then 'S2'
                when storecode = 'Y1'
                then 'S#'
            end as semester,
        from {{ ref("stg_powerschool__termbins") }}
        where storecode in ('Q1', 'Q2', 'Q3', 'Q4')

        union all

        select
            _dbt_source_relation,
            schoolid,
            yearid,
            'Y1' as storecode,
            firstday as term_start_date,
            lastday as term_end_date,

            false as is_current_term,
            'S#' as semester,
        from {{ ref("stg_powerschool__terms") }}
        where isyearrec = 1
    ),

    student_roster as (
        select
            enr._dbt_source_relation,
            enr.studentid,
            enr.student_number,
            enr.lastfirst,
            enr.enroll_status,
            enr.cohort,
            enr.gender,
            enr.ethnicity,

            enr.academic_year,
            enr.yearid,
            enr.region,
            enr.school_level,
            enr.schoolid,
            enr.school_abbreviation,
            enr.grade_level,
            enr.advisor_lastfirst,

            enr.year_in_school,
            enr.year_in_network,
            enr.rn_undergrad,
            enr.is_self_contained,
            enr.is_out_of_district,
            enr.is_retained_year,
            enr.is_retained_ever,
            enr.lunch_status,
            enr.lep_status,
            enr.is_504,

            term.storecode as term,
            term.term_start_date,
            term.term_end_date,
            term.is_current_term,
            term.semester,

            ktc.contact_id as salesforce_id,
            ktc.ktc_cohort,

            hos.head_of_school_preferred_name_lastfirst as head_of_school,

            gc.cumulative_y1_gpa,
            gc.cumulative_y1_gpa_unweighted,
            gc.cumulative_y1_gpa_projected,
            gc.cumulative_y1_gpa_projected_s1,
            gc.cumulative_y1_gpa_projected_s1_unweighted,
            gc.core_cumulative_y1_gpa,

            gt.gpa_term,
            gt.gpa_semester,
            gt.gpa_y1,
            gt.gpa_y1_unweighted,
            gt.total_credit_hours,
            gt.n_failing_y1,

            concat(enr.region, enr.school_level) as region_school_level,

            if(enr.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,
            if(
                enr.school_level in ('ES', 'MS'),
                enr.advisory_name,
                enr.advisor_lastfirst
            ) as advisory,

            if(sp.studentid is not null, 1, null) as is_counseling_services,

            if(sa.studentid is not null, 1, null) as is_student_athlete,

            round(ada.ada, 3) as ada,
        from {{ ref("base_powerschool__student_enrollments") }} as enr
        inner join
            term
            on enr.schoolid = term.schoolid
            and enr.yearid = term.yearid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="term") }}
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
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on enr.studentid = gc.studentid
            and enr.schoolid = gc.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="gc") }}
        left join
            {{ ref("int_powerschool__gpa_term") }} as gt
            on enr.studentid = gt.studentid
            and enr.yearid = gt.yearid
            and enr.schoolid = gt.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="gt") }}
            and term.storecode = gt.term_name
        where
            enr.academic_year >= {{ var("current_academic_year") - 1 }}
            and enr.rn_year = 1
            and not enr.is_out_of_district
            and enr.grade_level != 99
    ),

    course_enrollments as (
        select
            m._dbt_source_relation,
            m.cc_studentid as studentid,
            m.cc_yearid as yearid,
            m.cc_course_number as course_number,
            m.cc_sectionid as sectionid,
            m.cc_dateenrolled as date_enrolled,
            m.sections_dcid,
            m.sections_section_number as section_number,
            m.sections_external_expression as external_expression,
            m.sections_termid as termid,
            m.courses_credittype as credit_type,
            m.courses_course_name as course_name,
            m.courses_excludefromgpa as exclude_from_gpa,
            m.teachernumber as teacher_number,
            m.teacher_lastfirst,

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
            m.rn_course_number_year = 1
            and not m.is_dropped_section
            and m.cc_course_number not in (
                'LOG100',
                'LOG1010',
                'LOG11',
                'LOG12',
                'LOG20',
                'LOG22999XL',
                'LOG300',
                'LOG9',
                'SEM22106G1',
                'SEM22106S1'
            )
    ),

    y1_historical as (
        select
            tr._dbt_source_relation,
            tr.studentid,
            tr.academic_year,
            tr.yearid,
            tr.schoolid,
            tr.schoolname,
            tr.grade_level,
            tr.course_name,
            tr.sectionid,
            tr.teacher_name,
            tr.storecode,
            tr.termid,
            tr.percent,
            tr.grade,
            tr.earnedcrhrs,
            tr.potentialcrhrs,
            tr.gpa_points,
            tr.excludefromgpa,
            tr.is_transfer_grade,

            if(tr.is_transfer_grade, 'Transfer', tr.credit_type) as credit_type,
            if(
                tr.is_transfer_grade,
                concat(
                    'T',
                    upper(regexp_extract(tr._dbt_source_relation, r'(kipp\w+)_')),
                    tr.dcid
                ),
                tr.course_number
            ) as course_number,

            if(co.student_number is not null, true, false) as is_enrollment_matched,
        from {{ ref("stg_powerschool__storedgrades") }} as tr
        left join
            student_roster as co
            on tr.studentid = co.studentid
            and tr.academic_year = co.academic_year
            and tr.schoolid = co.schoolid
            and tr.storecode = co.term
            and {{ union_dataset_join_clause(left_alias="tr", right_alias="co") }}
        where tr.storecode = 'Y1'
    ),

    quarter_and_ip_y1_grades as (
        select
            _dbt_source_relation,
            studentid,
            yearid,
            schoolid,
            course_number,
            sectionid,
            termid,
            storecode,

            fg_percent,
            fg_letter_grade,
            fg_grade_points,
            fg_percent_adjusted,
            fg_letter_grade_adjusted,

            sg_percent,
            sg_letter_grade,
            sg_grade_points,

            term_percent_grade_adjusted,
            term_letter_grade_adjusted,
            term_grade_points,

            y1_percent_grade,
            y1_percent_grade_adjusted,
            y1_letter_grade,
            y1_letter_grade_adjusted,
            y1_grade_points,
            y1_grade_points_unweighted,

            need_60,
            need_70,
            need_80,
            need_90,

            citizenship,
            comment_value,
        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and not is_dropped_section
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')

        union all

        select
            _dbt_source_relation,
            studentid,
            yearid,
            schoolid,
            course_number,
            sectionid,
            termid,

            'Y1' as term,

            null as fg_percent,
            null as fg_letter_grade,
            null as fg_grade_points,
            null as fg_percent_adjusted,
            null as fg_letter_grade_adjusted,

            null as sg_percent,
            null as sg_letter_grade,
            null as sg_grade_points,

            term_percent_grade_adjusted,
            term_letter_grade_adjusted,
            term_grade_points,

            y1_percent_grade,
            y1_percent_grade_adjusted,
            y1_letter_grade,
            y1_letter_grade_adjusted,
            y1_grade_points,
            y1_grade_points_unweighted,

            need_60,
            need_70,
            need_80,
            need_90,

            null as citizenship,
            null as comment_value,
        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and termbin_is_current
            and not is_dropped_section
    ),

    category_grades as (
        select
            _dbt_source_relation,
            yearid,
            schoolid,
            studentid,
            course_number,
            sectionid,
            storecode_type,
            storecode,
            percent_grade,
            percent_grade_y1_running,

            concat('Q', storecode_order) as term,

            avg(if(is_current, percent_grade_y1_running, null)) over (
                partition by
                    _dbt_source_relation,
                    studentid,
                    yearid,
                    course_number,
                    storecode_type
            ) as category_percent_grade_y1_running_current_avg,

            round(
                avg(percent_grade) over (
                    partition by _dbt_source_relation, yearid, studentid, storecode
                ),
                2
            ) as category_quarter_average_all_courses,
        from {{ ref("int_powerschool__category_grades") }}
        where
            yearid >= {{ var("current_academic_year") - 1990 - 1 }}
            and not is_dropped_section
            and storecode_type not in ('Q', 'H')
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')
    )

select
    s._dbt_source_relation,
    s.studentid,
    s.student_number,
    s.salesforce_id,
    s.lastfirst,
    s.enroll_status,
    s.cohort,
    s.ktc_cohort,
    s.gender,
    s.ethnicity,

    s.academic_year,
    s.region,
    s.school_level,
    s.schoolid,
    s.school_abbreviation as school,
    s.grade_level,
    s.advisory,
    s.advisor_lastfirst as advisor_name,
    s.head_of_school as hos,
    s.region_school_level,

    s.year_in_school,
    s.year_in_network,
    s.rn_undergrad,
    s.is_out_of_district,
    s.is_self_contained as is_pathways,
    s.is_retained_year,
    s.is_retained_ever,
    s.lunch_status,
    s.iep_status,
    s.lep_status,
    s.is_504,
    s.is_counseling_services,
    s.is_student_athlete,

    s.ada,

    s.term as `quarter`,
    s.semester,
    s.term_start_date as quarter_start_date,
    s.term_end_date as quarter_end_date,
    s.term_end_date as cal_quarter_end_date,
    s.is_current_term as is_current_quarter,

    s.gpa_term as gpa_for_quarter,
    s.gpa_semester,
    s.gpa_y1,
    s.gpa_y1_unweighted,
    s.total_credit_hours as gpa_total_credit_hours,
    s.n_failing_y1 as gpa_n_failing_y1,

    s.cumulative_y1_gpa as gpa_cumulative_y1_gpa,
    s.cumulative_y1_gpa_unweighted as gpa_cumulative_y1_gpa_unweighted,
    s.cumulative_y1_gpa_projected as gpa_cumulative_y1_gpa_projected,
    s.cumulative_y1_gpa_projected_s1 as gpa_cumulative_y1_gpa_projected_s1,
    s.cumulative_y1_gpa_projected_s1_unweighted
    as gpa_cumulative_y1_gpa_projected_s1_unweighted,
    s.core_cumulative_y1_gpa as gpa_core_cumulative_y1_gpa,

    ce.sectionid,
    ce.sections_dcid,
    ce.section_number,
    ce.external_expression,
    ce.date_enrolled,
    ce.credit_type,
    ce.course_number,
    ce.course_name,
    ce.exclude_from_gpa,
    ce.teacher_number,
    ce.teacher_lastfirst as teacher_name,
    ce.tutoring_nj,
    ce.nj_student_tier,

    y1h.percent as y1_course_final_percent_grade_adjusted,
    y1h.grade as y1_course_final_letter_grade_adjusted,
    y1h.earnedcrhrs as y1_course_final_earned_credits,
    y1h.potentialcrhrs as y1_course_final_potential_credit_hours,
    y1h.gpa_points as y1_course_final_grade_points,

    qy1.fg_percent as quarter_course_in_progress_percent_grade,
    qy1.fg_letter_grade as quarter_course_in_progress_letter_grade,
    qy1.fg_grade_points as quarter_course_in_progress_grade_points,
    qy1.fg_percent_adjusted as quarter_course_in_progress_percent_grade_adjusted,
    qy1.fg_letter_grade_adjusted as quarter_course_in_progress_letter_grade_adjusted,
    qy1.sg_percent as quarter_course_final_percent_grade,
    qy1.sg_letter_grade as quarter_course_final_letter_grade,
    qy1.sg_grade_points as quarter_course_final_grade_points,
    qy1.term_percent_grade_adjusted as quarter_course_percent_grade_that_matters,
    qy1.term_letter_grade_adjusted as quarter_course_letter_grade_that_matters,
    qy1.term_grade_points as quarter_course_grade_points_that_matters,
    qy1.y1_percent_grade as y1_course_in_progress_percent_grade,
    qy1.y1_percent_grade_adjusted as y1_course_in_progress_percent_grade_adjusted,
    qy1.y1_letter_grade as y1_course_in_progress_letter_grade,
    qy1.y1_letter_grade_adjusted as y1_course_in_progress_letter_grade_adjusted,
    qy1.y1_grade_points as y1_course_in_progress_grade_points,
    qy1.y1_grade_points_unweighted as y1_course_in_progress_grade_points_unweighted,
    qy1.need_60,
    qy1.need_70,
    qy1.need_80,
    qy1.need_90,
    qy1.citizenship as quarter_citizenship,
    qy1.comment_value as quarter_comment_value,

    c.storecode_type as category_name_code,
    c.storecode as category_quarter_code,
    c.percent_grade as category_quarter_percent_grade,
    c.percent_grade_y1_running as category_y1_percent_grade_running,
    c.category_percent_grade_y1_running_current_avg
    as category_y1_percent_grade_current,
    c.category_quarter_average_all_courses,

    'Local' as roster_type,

    if(s.ada >= 0.80, 1, 0) as ada_above_or_at_80,

    if(
        s.grade_level < 9, ce.section_number, ce.external_expression
    ) as section_or_period,
from student_roster as s
left join
    course_enrollments as ce
    on s.studentid = ce.studentid
    and s.yearid = ce.yearid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="ce") }}
left join
    y1_historical as y1h
    on s.studentid = y1h.studentid
    and s.yearid = y1h.yearid
    and s.term = y1h.storecode
    and {{ union_dataset_join_clause(left_alias="s", right_alias="y1h") }}
    and ce.course_number = y1h.course_number
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="y1h") }}
left join
    quarter_and_ip_y1_grades as qy1
    on s.studentid = qy1.studentid
    and s.yearid = qy1.yearid
    and s.term = qy1.storecode
    and {{ union_dataset_join_clause(left_alias="s", right_alias="qy1") }}
    and ce.sectionid = qy1.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="qy1") }}
left join
    category_grades as c
    on s.studentid = c.studentid
    and s.yearid = c.yearid
    and s.term = c.term
    and {{ union_dataset_join_clause(left_alias="s", right_alias="c") }}
    and ce.sectionid = c.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="c") }}

union all

select
    e1._dbt_source_relation,
    e1.studentid,
    e1.student_number,
    e1.salesforce_id,
    e1.lastfirst,
    e1.enroll_status,
    e1.cohort,
    e1.ktc_cohort,
    e1.gender,
    e1.ethnicity,

    e1.academic_year,
    e1.region,
    e1.school_level,
    e1.schoolid,
    e1.school_abbreviation as school,
    e1.grade_level,
    e1.advisory,
    e1.advisor_lastfirst as advisor_name,
    e1.head_of_school as hos,
    e1.region_school_level,

    e1.year_in_school,
    e1.year_in_network,
    e1.rn_undergrad,
    e1.is_out_of_district,
    e1.is_self_contained as is_pathways,
    e1.is_retained_year,
    e1.is_retained_ever,
    e1.lunch_status,
    e1.iep_status,
    e1.lep_status,
    e1.is_504,
    e1.is_counseling_services,
    e1.is_student_athlete,

    e1.ada,

    e1.term as `quarter`,
    e1.semester,
    e1.term_start_date as quarter_start_date,
    e1.term_end_date as quarter_end_date,
    e1.term_end_date as cal_quarter_end_date,
    e1.is_current_term as is_current_quarter,

    e1.gpa_term as gpa_for_quarter,
    e1.gpa_semester,
    e1.gpa_y1,
    e1.gpa_y1_unweighted,
    e1.total_credit_hours as gpa_total_credit_hours,
    e1.n_failing_y1 as gpa_n_failing_y1,

    e1.cumulative_y1_gpa as gpa_cumulative_y1_gpa,
    e1.cumulative_y1_gpa_unweighted as gpa_cumulative_y1_gpa_unweighted,
    e1.cumulative_y1_gpa_projected as gpa_cumulative_y1_gpa_projected,
    e1.cumulative_y1_gpa_projected_s1 as gpa_cumulative_y1_gpa_projected_s1,
    e1.cumulative_y1_gpa_projected_s1_unweighted
    as gpa_cumulative_y1_gpa_projected_s1_unweighted,
    e1.core_cumulative_y1_gpa as gpa_core_cumulative_y1_gpa,

    null as sectionid,
    null as sections_dcid,
    null as section_number,
    null as external_expression,
    null as date_enrolled,

    y1h.credit_type,
    y1h.course_number,
    y1h.course_name,
    y1h.excludefromgpa as exclude_from_gpa,

    null as teacher_number,

    y1h.teacher_name,

    null as tutoring_nj,
    null as nj_student_tier,

    y1h.percent as y1_course_final_percent_grade_adjusted,
    y1h.grade as y1_course_final_letter_grade_adjusted,
    y1h.earnedcrhrs as y1_course_final_earned_credits,
    y1h.potentialcrhrs as y1_course_final_potential_credit_hours,
    y1h.gpa_points as y1_course_final_grade_points,

    null as quarter_course_in_progress_percent_grade,
    null as quarter_course_in_progress_letter_grade,
    null as quarter_course_in_progress_grade_points,
    null as quarter_course_in_progress_percent_grade_adjusted,
    null as quarter_course_in_progress_letter_grade_adjusted,
    null as quarter_course_final_percent_grade,
    null as quarter_course_final_letter_grade,
    null as quarter_course_final_grade_points,
    null as quarter_course_percent_grade_that_matters,
    null as quarter_course_letter_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    null as y1_course_in_progress_percent_grade,
    null as y1_course_in_progress_percent_grade_adjusted,
    null as y1_course_in_progress_letter_grade,
    null as y1_course_in_progress_letter_grade_adjusted,
    null as y1_course_in_progress_grade_points,
    null as y1_course_in_progress_grade_points_unweighted,
    null as need_60,
    null as need_70,
    null as need_80,
    null as need_90,
    null as quarter_citizenship,
    null as quarter_comment_value,
    null as category_name_code,
    null as category_quarter_code,
    null as category_quarter_percent_grade,
    null as category_y1_percent_grade_running,
    null as category_y1_percent_grade_current,
    null as category_quarter_average_all_courses,

    'Transfer' as roster_type,

    null as ada_above_or_at_80,
    null as section_or_period,
from y1_historical as y1h
inner join
    student_roster as e1
    on y1h.studentid = e1.studentid
    and y1h.schoolid = e1.schoolid
    and y1h.storecode = e1.term
    and {{ union_dataset_join_clause(left_alias="y1h", right_alias="e1") }}
    and e1.year_in_school = 1
where y1h.is_transfer_grade and not y1h.is_enrollment_matched
