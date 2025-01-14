with
    ms_grad_sub as (
        select
            _dbt_source_relation,
            student_number,
            school_abbreviation as ms_attended,

            row_number() over (
                partition by student_number order by exitdate desc
            ) as rn,
        from {{ ref("base_powerschool__student_enrollments") }}
        where school_level = 'MS'
    )

select
    e._dbt_source_relation,
    e.academic_year,
    e.yearid,
    e.region,
    e.school_level,
    e.schoolid,
    e.school_name,
    e.school_abbreviation as school,
    e.studentid,
    e.students_dcid,
    e.student_number,
    e.lastfirst as student_name,
    e.last_name as student_last_name,
    e.first_name as student_first_name,
    e.grade_level,
    e.gender,
    e.ethnicity,
    e.enroll_status,
    e.entrydate,
    e.exitdate,
    e.cohort,
    e.is_504,
    e.lep_status,
    e.lunch_status,
    e.gifted_and_talented,
    e.is_homeless,
    e.dob,
    e.boy_status,
    e.is_out_of_district,
    e.is_self_contained,
    e.is_enrolled_recent,
    e.is_enrolled_y1,
    e.is_retained_year,
    e.is_retained_ever,
    e.year_in_school,
    e.year_in_network,
    e.rn_undergrad,
    e.student_email_google as student_email,
    e.code_location,

    m.ms_attended,

    adb.contact_id as salesforce_id,
    adb.ktc_cohort,
    adb.contact_owner_name,
    adb.contact_df_has_fafsa as has_fafsa,
    adb.contact_college_match_display_gpa as college_match_gpa,

    hr.sections_section_number as team,

    hos.head_of_school_preferred_name_lastfirst as hos,

    'KTAF' as district,

    concat(e.region, e.school_level) as region_school_level,

    coalesce(e.contact_1_email_current, e.contact_2_email_current) as guardian_email,

    cast(e.academic_year as string)
    || '-'
    || right(cast(e.academic_year + 1 as string), 2) as academic_year_display,

    round(ada.ada, 3) as ada,

    if(e.region = 'Miami', e.fleid, e.state_studentnumber) as state_studentnumber,

    if(e.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

    if(sp.studentid is not null, 1, null) as is_counseling_services,

    if(sa.studentid is not null, 1, null) as is_student_athlete,

    if(tut.studentid is not null, true, false) as is_tutoring,

    if(round(ada.ada, 3) >= 0.80, true, false) as ada_above_or_at_80,

    case
        e.ethnicity when 'T' then 'T' when 'H' then 'H' else e.ethnicity
    end as race_ethnicity,

    case
        when e.school_level in ('ES', 'MS')
        then e.advisory_name
        when e.school_level = 'HS'
        then e.advisor_lastfirst
    end as advisory,

    case
        when e.region in ('Camden', 'Newark')
        then 'NJ'
        when e.region = 'Miami'
        then 'FL'
    end as `state`,

    case
        when adb.contact_college_match_display_gpa >= 3.50
        then '3.50+'
        when adb.contact_college_match_display_gpa >= 3.00
        then '3.00-3.49'
        when adb.contact_college_match_display_gpa >= 2.50
        then '2.50-2.99'
        when adb.contact_college_match_display_gpa >= 2.00
        then '2.00-2.49'
        when adb.contact_college_match_display_gpa < 2.00
        then '<2.00'
        else 'No GPA'
    end as college_match_gpa_bands,
from {{ ref("base_powerschool__student_enrollments") }} as e
left join
    ms_grad_sub as m
    on e.student_number = m.student_number
    and {{ union_dataset_join_clause(left_alias="e", right_alias="m") }}
    and m.rn = 1
left join
    {{ ref("int_kippadb__roster") }} as adb on e.student_number = adb.student_number
left join
    {{ ref("int_powerschool__spenrollments") }} as sp
    on e.studentid = sp.studentid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="sp") }}
    and current_date('{{ var("local_timezone") }}')
    between sp.enter_date and sp.exit_date
    and sp.specprog_name = 'Counseling Services'
left join
    {{ ref("int_powerschool__spenrollments") }} as sa
    on e.studentid = sa.studentid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="sa") }}
    and current_date('{{ var("local_timezone") }}')
    between sa.enter_date and sa.exit_date
    and sa.specprog_name = 'Student Athlete'
left join
    {{ ref("int_powerschool__spenrollments") }} as tut
    on e.studentid = sa.studentid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="tut") }}
    and current_date('{{ var("local_timezone") }}')
    between tut.enter_date and tut.exit_date
    and tut.specprog_name = 'Tutoring'
left join
    {{ ref("base_powerschool__course_enrollments") }} as hr
    on e.student_number = hr.students_student_number
    and e.yearid = hr.cc_yearid
    and e.schoolid = hr.cc_schoolid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="hr") }}
    and not hr.is_dropped_section
    and hr.courses_credittype = 'HR'
    and hr.rn_course_number_year = 1
left join
    {{ ref("int_powerschool__ada") }} as ada
    on e.studentid = ada.studentid
    and e.yearid = ada.yearid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ada") }}
left join
    {{ ref("int_people__leadership_crosswalk") }} as hos
    on e.schoolid = hos.home_work_location_powerschool_school_id
where e.rn_year = 1 and e.schoolid != 999999
