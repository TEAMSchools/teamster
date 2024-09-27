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
    e.contact_1_email_current as guardian_email,
    e.student_email_google as student_email,

    m.ms_attended,

    adb.contact_id,
    adb.ktc_cohort,
    adb.contact_owner_name,
    adb.contact_df_has_fafsa as has_fafsa,

    hr.sections_section_number as team,

    'KTAF' as district,

    cast(e.academic_year as string)
    || '-'
    || right(cast(e.academic_year + 1 as string), 2) as academic_year_display,

    case
        e.ethnicity when 'T' then 'T' when 'H' then 'H' else e.ethnicity
    end as race_ethnicity,

    if(e.region = 'Miami', e.fleid, e.state_studentnumber) as state_studentnumber,
    if(e.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

    if(sp.studentid is not null, 1, null) as is_counseling_services,

    if(sa.studentid is not null, 1, null) as is_student_athlete,

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
    {{ ref("base_powerschool__course_enrollments") }} as hr
    on e.student_number = hr.students_student_number
    and e.yearid = hr.cc_yearid
    and e.schoolid = hr.cc_schoolid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="hr") }}
    and not hr.is_dropped_section
    and hr.cc_course_number = 'HR'
    and hr.rn_course_number_year = 1
where e.rn_year = 1 and e.schoolid != 999999
