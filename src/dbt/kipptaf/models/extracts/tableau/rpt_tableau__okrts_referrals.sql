with
    suspension_type as (
        select penalty_name, 'ISS' as suspension_type,
        from
            unnest(
                [
                    'In School Suspension',
                    'KM: In-School Suspension',
                    'KNJ: In-School Suspension'
                ]
            ) as penalty_name

        union all

        select penalty_name, 'OSS' as suspension_type,
        from
            unnest(
                [
                    'Out of School Suspension',
                    'KM: Out-of-School Suspension',
                    'KNJ: Out-of-School Suspension'
                ]
            ) as penalty_name
    )

select
    co.student_number,
    co.lastfirst as student_name,
    co.academic_year,
    co.schoolid,
    co.school_abbreviation as school,
    co.region,
    co.grade_level,
    co.enroll_status,
    co.cohort,
    co.school_level,
    co.gender,
    co.ethnicity,
    co.lunch_status,
    co.is_retained_year,

    w.week_start_monday,
    w.week_end_sunday,
    w.date_count as days_in_session,
    w.quarter as term,

    dli.incident_id,
    dli.create_ts_date,
    dli.category,
    dli.reported_details,
    dli.admin_summary,

    dlp.num_days,
    dlp.is_suspension,

    cf.nj_state_reporting,
    cf.restraint_used,
    cf.ssds_incident_id,

    st.suspension_type,

    if(co.lep_status, 'ML', 'Not ML') as ml_status,
    if(co.is_504, 'Has 504', 'No 504') as status_504,
    if(
        co.is_self_contained, 'Self-contained', 'Not self-contained'
    ) as self_contained_status,
    if(co.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

    concat(dli.create_last, ', ', dli.create_first) as entry_staff,
    concat(dli.update_last, ', ', dli.update_first) as last_update_staff,
    case
        when left(dli.category, 2) = 'SW'
        then 'Social Work'
        when left(dli.category, 2) = 'TX'
        then 'Home Instruction Request'
        when left(dli.category, 2) = 'Low'
        then 'Tier 1'
        when left(dli.category, 2) = 'Middle'
        then 'Tier 2'
        when left(dli.category, 2) = 'High'
        then 'Tier 3'
        when dli.category is null
        then null
        else 'Other'
    end as referral_tier,

    row_number() over (
        partition by co.academic_year, co.student_number, dli.incident_id
        order by dlp.is_suspension desc
    ) as rn_incident,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("int_powerschool__calendar_week") }} as w
    on co.academic_year = w.academic_year
    and co.schoolid = w.schoolid
    and w.week_end_sunday between co.entrydate and co.exitdate
left join
    {{ ref("stg_deanslist__incidents") }} as dli
    on co.student_number = dli.student_school_id
    and co.academic_year = dli.create_ts_academic_year
    and extract(date from dli.create_ts_date)
    between w.week_start_monday and w.week_end_sunday
    and {{ union_dataset_join_clause(left_alias="co", right_alias="dli") }}
left join
    {{ ref("stg_deanslist__incidents__penalties") }} as dlp
    on dli.incident_id = dlp.incident_id
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="dlp") }}
left join
    {{ ref("int_deanslist__incidents__custom_fields__pivot") }} as cf
    on dli.incident_id = cf.incident_id
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="cf") }}
left join suspension_type as st on dlp.penalty_name = st.penalty_name
where
    co.academic_year >= {{ var("current_academic_year") }} - 1
    and co.rn_year = 1
    and co.grade_level != 99
