{{- config(materialized="table") -}}

with
    term as ( -- NEED TO CHANGE THIS TO USE THE WEEK TABLE SO CAN GET THE CORRECT START/END DATES AND BRING WEEK NUMBER.... OR ADD WEEK CALENDAR TO THIS!
        select
            t._dbt_source_relation,
            t.schoolid,
            t.yearid,

            tb.storecode,
            tb.date1 as term_start_date,
            tb.date2 as term_end_date,

            if(
                current_date('America/New_York') between tb.date1 and tb.date2,
                true,
                false
            ) as is_current_term,

            case
                when tb.storecode in ('Q1', 'Q2')
                then 'S1'
                when tb.storecode in ('Q3', 'Q4')
                then 'S2'
            end as semester,
        from {{ ref("stg_powerschool__terms") }} as t
        inner join
            {{ ref("stg_powerschool__termbins") }} as tb
            on t.id = tb.termid
            and t.schoolid = tb.schoolid
            and {{ union_dataset_join_clause(left_alias="t", right_alias="tb") }}
            and tb.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
        where t.isyearrec = 1
    ),

    student_roster as (
        select
            enr._dbt_source_relation,
            enr.studentid,
            enr.student_number,
            enr.student_name,
            enr.enroll_status,
            enr.cohort,
            enr.gender,
            enr.ethnicity,
            enr.academic_year,
            enr.academic_year_display,
            enr.yearid,
            enr.region,
            enr.school_level,
            enr.schoolid,
            enr.school,
            enr.grade_level,
            enr.advisory,
            enr.year_in_school,
            enr.year_in_network,
            enr.rn_undergrad,
            enr.is_self_contained as is_pathways,
            enr.is_out_of_district,
            enr.is_retained_year,
            enr.is_retained_ever,
            enr.lunch_status,
            enr.lep_status,
            enr.gifted_and_talented,
            enr.iep_status,
            enr.is_504,
            enr.contact_id as salesforce_id,
            enr.ktc_cohort,
            enr.is_counseling_services,
            enr.is_student_athlete,

            term.storecode as `quarter`,
            term.term_start_date as quarter_start_date,
            term.term_end_date as quarter_end_date,
            term.term_end_date as cal_quarter_end_date,
            term.is_current_term as is_current_quarter,
            term.semester,

            hos.head_of_school_preferred_name_lastfirst as hos,

            concat(enr.region, enr.school_level) as region_school_level,

            round(ada.ada, 3) as ada,

            if(
                current_date('America/New_York')
                between (term.term_end_date - 3) and (term.term_start_date + 14),
                true,
                false
            ) as is_quarter_end_date_range,

        from {{ ref("int_tableau__student_enrollments") }} as enr
        inner join
            term
            on enr.schoolid = term.schoolid
            and enr.yearid = term.yearid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="term") }}
        left join
            {{ ref("int_people__leadership_crosswalk") }} as hos
            on enr.schoolid = hos.home_work_location_powerschool_school_id
        left join
            {{ ref("int_powerschool__ada") }} as ada
            on enr.studentid = ada.studentid
            and enr.yearid = ada.yearid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="ada") }}
        where
            not enr.is_out_of_district
            and enr.enroll_status = 0
            and enr.academic_year = {{ var("current_academic_year") }}
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
            m.teacher_lastfirst as teacher_name,

            f.tutoring_nj,
            f.nj_student_tier,

            if(m.ap_course_subject is not null, true, false) as is_ap_course,
        from {{ ref("base_powerschool__course_enrollments") }} as m
        left join
            {{ ref("int_reporting__student_filters") }} as f
            on m.cc_studentid = f.studentid
            and m.cc_academic_year = f.academic_year
            and m.courses_credittype = f.powerschool_credittype
            and {{ union_dataset_join_clause(left_alias="m", right_alias="f") }}
        where
            m.rn_course_number_year = 1
            and m.cc_sectionid > 0
            and m.cc_course_number not in (
                'LOG100',  -- Lunch
                'LOG1010',  -- Lunch
                'LOG11',  -- Lunch
                'LOG12',  -- Lunch
                'LOG20',  -- Early Dismissal
                'LOG22999XL',  -- Lunch
                'LOG300',  -- Study Hall
                'LOG9',  -- Lunch
                'SEM22106G1',  -- Advisory
                'SEM22106S1'  -- Not in SY24-25 yet
            )
    )

select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level,
    s.salesforce_id,
    s.ktc_cohort,
    s.enroll_status,
    s.cohort,
    s.gender,
    s.ethnicity,
    s.advisory,
    s.hos,
    s.region_school_level,
    s.year_in_school,
    s.year_in_network,
    s.rn_undergrad,
    s.is_out_of_district,
    s.is_pathways,
    s.is_retained_year,
    s.is_retained_ever,
    s.lunch_status,
    s.gifted_and_talented,
    s.iep_status,
    s.lep_status,
    s.is_504,
    s.is_counseling_services,
    s.is_student_athlete,
    s.ada,
    s.`quarter`,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.cal_quarter_end_date,
    s.is_current_quarter,
    s.is_quarter_end_date_range,

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
    ce.teacher_name,
    ce.tutoring_nj,
    ce.nj_student_tier,
    ce.is_ap_course,

    r.sam_account_name as tableau_username,

    if(s.ada >= 0.80, true, false) as ada_above_or_at_80,

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
    {{ ref("base_people__staff_roster") }} as r
    on ce.teacher_number = r.powerschool_teacher_number
/*left join
    {{ ref("stg_reporting__gradebook_expectations") }} as ge
    on s.academic_year = ge.academic_year
    and s.region = ge.region
    and s.quarter = ge.quarter
    and s.school_level = ge.school_level*/
where s.quarter_start_date <= current_date('America/New_York')
