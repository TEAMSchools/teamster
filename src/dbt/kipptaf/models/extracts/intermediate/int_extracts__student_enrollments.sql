{{- config(materialized="table") -}}

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
    ),

    mia_territory as (
        select
            r._dbt_source_relation,
            r.roster_name as territory,

            a.student_school_id,

            row_number() over (
                partition by a.student_school_id order by r.roster_id asc
            ) as rn_territory,
        from {{ ref("stg_deanslist__rosters") }} as r
        inner join
            {{ ref("stg_deanslist__roster_assignments") }} as a
            on r.roster_id = a.dl_roster_id
        where r.school_id = 472 and r.roster_type = 'House' and r.active = 'Y'
    )

select
    e._dbt_source_relation,
    e.academic_year,
    e.yearid,
    e.entrydate,
    e.exitdate,
    e.region,
    e.school_level,
    e.schoolid,
    e.school_name,
    e.school_abbreviation as school,
    e.grade_level,
    e.studentid,
    e.students_dcid,
    e.student_number,
    e.lastfirst as student_name,
    e.last_name as student_last_name,
    e.first_name as student_first_name,
    e.student_email_google as student_email,
    e.enroll_status,
    e.cohort,
    e.gender,
    e.ethnicity,
    e.dob,
    e.lunch_status,
    e.special_education_code,
    e.lep_status,
    e.gifted_and_talented,
    e.is_504,
    e.is_homeless,
    e.is_out_of_district,
    e.is_self_contained,
    e.is_enrolled_oct01,
    e.is_enrolled_recent,
    e.is_enrolled_y1,
    e.is_retained_year,
    e.is_retained_ever,
    e.year_in_school,
    e.year_in_network,
    e.boy_status,
    e.rn_undergrad,
    e.rn_year,
    e.code_location,

    m.ms_attended,

    mt.territory,

    adb.id as salesforce_id,
    adb.df_has_fafsa as has_fafsa,
    adb.college_match_display_gpa as college_match_gpa,

    su.name as contact_owner_name,

    hr.sections_section_number as team,

    hos.head_of_school_preferred_name_lastfirst as hos,

    'KTAF' as district,

    coalesce(adb.kipp_hs_class, e.cohort) as ktc_cohort,

    concat(e.region, e.school_level) as region_school_level,
    coalesce(e.contact_1_email_current, e.contact_2_email_current) as guardian_email,
    cast(e.academic_year as string)
    || '-'
    || right(cast(e.academic_year + 1 as string), 2) as academic_year_display,

    round(ada.ada, 3) as ada,

    if(e.region = 'Miami', e.fleid, e.state_studentnumber) as state_studentnumber,
    if(e.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

    if(
        current_date('{{ var("local_timezone") }}')
        between cs.enter_date and cs.exit_date,
        1,
        null
    ) as is_counseling_services,

    if(
        current_date('{{ var("local_timezone") }}')
        between ath.enter_date and ath.exit_date,
        1,
        null
    ) as is_student_athlete,

    if(
        current_date('{{ var("local_timezone") }}')
        between tut.enter_date and tut.exit_date,
        true,
        false
    ) as is_tutoring,

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
        when adb.college_match_display_gpa >= 3.50
        then '3.50+'
        when adb.college_match_display_gpa >= 3.00
        then '3.00-3.49'
        when adb.college_match_display_gpa >= 2.50
        then '2.50-2.99'
        when adb.college_match_display_gpa >= 2.00
        then '2.00-2.49'
        when adb.college_match_display_gpa < 2.00
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
    mia_territory as mt
    on e.student_number = mt.student_school_id
    and {{ union_dataset_join_clause(left_alias="e", right_alias="mt") }}
    and mt.rn_territory = 1
left join
    {{ ref("stg_kippadb__contact") }} as adb
    on e.student_number = adb.school_specific_id
left join {{ ref("stg_kippadb__user") }} as su on adb.owner_id = su.id
left join
    {{ ref("int_powerschool__spenrollments") }} as cs
    on e.studentid = cs.studentid
    and e.academic_year = cs.academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="cs") }}
    and cs.specprog_name = 'Counseling Services'
left join
    {{ ref("int_powerschool__spenrollments") }} as ath
    on e.studentid = ath.studentid
    and e.academic_year = ath.academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ath") }}
    and ath.specprog_name = 'Student Athlete'
left join
    {{ ref("int_powerschool__spenrollments") }} as tut
    on e.studentid = tut.studentid
    and e.academic_year = tut.academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="tut") }}
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
where e.schoolid != 999999
