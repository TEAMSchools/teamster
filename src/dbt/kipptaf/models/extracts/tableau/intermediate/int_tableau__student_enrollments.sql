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

    dlm as (
        select distinct student_number,
        from {{ ref("int_students__graduation_path_codes") }}
        where code = 'M'
    )

select
    e._dbt_source_relation,
    e.academic_year,
    e.region,
    e.schoolid,
    e.school_abbreviation as school,
    e.studentid,
    e.student_number,
    e.lastfirst as student_name,
    e.grade_level,
    e.gender,
    e.enroll_status,
    e.cohort,
    e.is_out_of_district,
    e.is_self_contained,
    e.lunch_status,
    e.gifted_and_talented,

    m.ms_attended,

    adb.contact_id,
    adb.ktc_cohort,
    adb.contact_owner_name,

    'KTAF' as district,

    if(e.region = 'Miami', e.fleid, e.state_studentnumber) as state_studentnumber,
    if(e.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,
    if(d.student_number is null, false, true) as dlm,
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
left join dlm as d on e.student_number = d.student_number
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
where e.rn_year = 1 and e.schoolid != 999999
