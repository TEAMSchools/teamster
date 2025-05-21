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
    ),

    overgrad_fafsa as (
        select
            p._dbt_source_relation,

            if(
                p.fafsa_status = 'FAFSA Complete, Good to Go', 'Yes', 'No'
            ) as overgrad_has_fafsa,

            if(p.fafsa_opt_out is null, 'No', 'Yes') as overgrad_fafsa_opt_out,

            s.external_student_id as salesforce_contact_id,

        from {{ ref("int_overgrad__custom_fields_pivot") }} as p
        inner join
            {{ ref("stg_overgrad__students") }} as s
            on p.id = s.id
            and {{ union_dataset_join_clause(left_alias="p", right_alias="s") }}
        where p._dbt_source_model = 'stg_overgrad__students'
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
    e.is_fldoe_fte_all,
    e.year_in_school,
    e.year_in_network,
    e.boy_status,
    e.rn_undergrad,
    e.code_location,
    e.salesforce_contact_id as salesforce_id,
    e.salesforce_contact_df_has_fafsa as has_fafsa,
    e.salesforce_contact_college_match_display_gpa as college_match_gpa,
    e.salesforce_contact_college_match_gpa_band as college_match_gpa_bands,
    e.salesfoce_contact_owner_name as contact_owner_name,
    e.ktc_cohort,
    e.illuminate_student_id,

    m.ms_attended,

    mt.territory,

    hr.sections_section_number as team,

    hos.head_of_school_preferred_name_lastfirst as hos,

    ovg.overgrad_has_fafsa,
    ovg.overgrad_fafsa_opt_out,

    'KTAF' as district,

    concat(e.region, e.school_level) as region_school_level,

    coalesce(e.contact_1_email_current, e.contact_2_email_current) as guardian_email,

    cast(e.academic_year as string)
    || '-'
    || right(cast(e.academic_year + 1 as string), 2) as academic_year_display,

    round(ada.ada, 3) as ada,

    if(
        e.salesforce_contact_df_has_fafsa = 'Yes' or ovg.overgrad_has_fafsa = 'Yes',
        true,
        false
    ) as overall_has_fafsa,

    if(
        e.salesforce_contact_df_has_fafsa = 'Yes'
        or ovg.overgrad_has_fafsa = 'Yes'
        or ovg.overgrad_fafsa_opt_out = 'Yes',
        true,
        false
    ) as met_fafsa_requirement,

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
left join
    overgrad_fafsa as ovg
    on e.salesforce_contact_id = ovg.salesforce_contact_id
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ovg") }}
where e.rn_year = 1 and e.schoolid != 999999
