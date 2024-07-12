with
    nj_state_assessment_demo as (
        select distinct
            _dbt_source_relation,
            academic_year,
            statestudentidentifier as state_id,

            coalesce(studentwithdisabilities in ('504', 'B'), false) as is_504,

            if(englishlearnerel = 'Y', true, false) as lep_status,

            case
                when twoormoreraces = 'Y'
                then 'T'
                when hispanicorlatinoethnicity = 'Y'
                then 'H'
                when americanindianoralaskanative = 'Y'
                then 'I'
                when asian = 'Y'
                then 'A'
                when blackorafricanamerican = 'Y'
                then 'B'
                when nativehawaiianorotherpacificislander = 'Y'
                then 'P'
                when white = 'Y'
                then 'W'
            end as race_ethnicity,

            case
                when studentwithdisabilities in ('IEP', 'B')
                then 'Has IEP'
                else 'No IEP'
            end as iep_status,

        from {{ ref("int_pearson__all_assessments") }}
        where academic_year >= {{ var("current_academic_year") - 7 }}
    ),

    students as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.region,
            e.schoolid,
            e.school_abbreviation as school,
            e.student_number,
            e.lastfirst as student_name,
            e.grade_level,
            e.cohort,
            e.enroll_status,
            e.is_out_of_district,
            e.gender,
            e.lunch_status,

            if(e.region = 'Miami', e.lep_status, d.lep_status) as lep_status,
            if(e.region = 'Miami', e.is_504, d.is_504) as is_504,

            if(
                e.region = 'Miami', e.fleid, e.state_studentnumber
            ) as state_studentnumber,

            case
                when e.region != 'Miami'
                then d.race_ethnicity
                when e.region = 'Miami' and e.ethnicity = 'T'
                then 'T'
                when e.region = 'Miami' and e.ethnicity = 'H'
                then 'H'
                when e.region = 'Miami'
                then e.ethnicity
            end as race_ethnicity,

            case
                when e.region != 'Miami'
                then d.iep_status
                when e.region = 'Miami' and e.spedlep like '%SPED%'
                then 'Has IEP'
                else 'No IEP'
            end as iep_status,

            case
                when e.school_level in ('ES', 'MS')
                then e.advisory_name
                when e.school_level = 'HS'
                then e.advisor_lastfirst
            end as advisory,

        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            nj_state_assessment_demo as d
            on e.academic_year = d.academic_year
            and e.state_studentnumber = d.state_id
        where e.rn_year = 1 and e.schoolid != 999999
    )

select *
from students
