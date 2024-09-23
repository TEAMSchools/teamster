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
    ),

    intervention_rosters as (
        select ra.student_school_id,
        from {{ ref("stg_deanslist__roster_assignments") }} as ra
        inner join
            {{ ref("stg_deanslist__rosters") }} as r
            on ra.dl_roster_id = r.roster_id
            and r.roster_name = 'Tier 3/Tier 4 Intervention'
    ),

    att_reconciliation_rollup as (
        select
            ra.student_id as student_number,

            lc.powerschool_school_id as schoolid,

            count(*) as att_discrepancy_count,
        from {{ ref("stg_deanslist__reconcile_attendance") }} as ra
        inner join
            {{ ref("stg_people__location_crosswalk") }} as lc
            on ra.school_name = lc.name
        group by ra.student_id, lc.powerschool_school_id
    ),

    suspension_reconciliation_rollup as (
        select
            rs.student_id as student_number,
            rs.dl_incident_id as incident_id,

            lc.powerschool_school_id as schoolid,

            row_number() over (
                partition by rs.student_id, rs.dl_incident_id, lc.powerschool_school_id
                order by rs.consequence desc
            ) as rn_incident,
        from {{ ref("stg_deanslist__reconcile_suspensions") }} as rs
        inner join
            {{ ref("stg_people__location_crosswalk") }} as lc
            on rs.school_name = lc.name
    )

select
    co.student_number,
    co.lastfirst as student_name,
    co.academic_year,
    co.schoolid,
    co.school_abbreviation as school,
    co.school_name,
    co.region,
    co.grade_level,
    co.enroll_status,
    co.cohort,
    co.school_level,
    co.gender,
    co.ethnicity,
    co.lunch_status,
    co.is_retained_year,
    co.rn_year,

    hr.sections_section_number as homeroom_section,
    hr.teacher_lastfirst as homeroom_teacher_name,

    w.week_start_monday,
    w.week_end_sunday,
    w.date_count as days_in_session,
    w.quarter as term,

    dli.incident_id,
    dli.create_ts_date,
    dli.category,
    dli.reported_details,
    dli.admin_summary,

    dlp.incident_penalty_id,
    dlp.num_days,
    dlp.is_suspension,
    dlp.penalty_name,
    dlp.start_date,
    dlp.end_date,

    cf.nj_state_reporting,
    cf.restraint_used,
    cf.ssds_incident_id,

    st.suspension_type,

    ada.days_absent_unexcused,

    gpa.gpa_y1,

    ar.att_discrepancy_count,

    if(sr.incident_id is not null, true, false) as is_discrepant_incident,

    if(co.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,
    if(co.lep_status, 'ML', 'Not ML') as ml_status,
    if(co.is_504, 'Has 504', 'No 504') as status_504,
    if(
        co.is_self_contained, 'Self-contained', 'Not self-contained'
    ) as self_contained_status,

    concat(dli.create_last, ', ', dli.create_first) as entry_staff,
    concat(dli.update_last, ', ', dli.update_first) as last_update_staff,
    case
        when left(dli.category, 2) in ('SW', 'SSC')
        then 'Social Work'
        when left(dli.category, 2) = 'TX'
        then 'Non-Behavioral'
        when left(dli.category, 2) = 'TB'
        then 'Bus Referral (Miami)'
        when left(dli.category, 2) = 'T1' or left(dli.category, 6) = 'Tier 1'
        then 'Low'
        when left(dli.category, 2) = 'T2' or left(dli.category, 6) = 'Tier 2'
        then 'Middle'
        when left(dli.category, 2) = 'T3' or left(dli.category, 6) = 'Tier 3'
        then 'High'
        when dli.category is null
        then null
        else 'Other'
    end as referral_tier,

    round(ada.ada, 2) as ada,
    if(round(ada.ada, 2) <= 0.90, true, false) as is_chronically_absent,

    count(distinct co.student_number) over (
        partition by w.week_start_monday, co.school_abbreviation
    ) as school_enrollment_by_week,

    max(if(dlp.is_suspension, 1, 0)) over (
        partition by co.academic_year, co.student_number
    ) as is_suspended_y1_int,

    max(if(st.suspension_type = 'OSS', 1, 0)) over (
        partition by co.academic_year, co.student_number
    ) as is_suspended_y1_oss_int,

    max(if(st.suspension_type = 'ISS', 1, 0)) over (
        partition by co.academic_year, co.student_number
    ) as is_suspended_y1_iss_int,

    if(tr.student_school_id is not null, true, false) as is_tier3_4,

    row_number() over (
        partition by co.academic_year, co.student_number
        order by w.week_start_monday asc
    ) as rn_student_year,

    if(
        dli.incident_id is null,
        null,
        row_number() over (
            partition by co.academic_year, co.student_number, dli.incident_id
            order by dlp.is_suspension desc
        )
    ) as rn_incident,
from {{ ref("base_powerschool__student_enrollments") }} as co
left join
    {{ ref("base_powerschool__course_enrollments") }} as hr
    on co.studentid = hr.cc_studentid
    and co.yearid = hr.cc_yearid
    and co.schoolid = hr.cc_schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="hr") }}
    and hr.cc_course_number = 'HR'
    and hr.rn_course_number_year = 1
    and not hr.is_dropped_section
inner join
    {{ ref("int_powerschool__calendar_week") }} as w
    on co.academic_year = w.academic_year
    and co.schoolid = w.schoolid
    and w.week_end_sunday between co.entrydate and co.exitdate
    and {{ union_dataset_join_clause(left_alias="co", right_alias="w") }}
left join
    {{ ref("stg_deanslist__incidents") }} as dli
    on co.student_number = dli.student_school_id
    and co.academic_year = dli.create_ts_academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="dli") }}
    and extract(date from dli.create_ts_date)
    between w.week_start_monday and w.week_end_sunday
    and {{ union_dataset_join_clause(left_alias="w", right_alias="dli") }}
left join
    {{ ref("stg_deanslist__incidents__penalties") }} as dlp
    on dli.incident_id = dlp.incident_id
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="dlp") }}
left join
    {{ ref("int_deanslist__incidents__custom_fields__pivot") }} as cf
    on dli.incident_id = cf.incident_id
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="cf") }}
left join suspension_type as st on dlp.penalty_name = st.penalty_name
left join
    {{ ref("int_powerschool__ada") }} as ada
    on co.studentid = ada.studentid
    and co.yearid = ada.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ada") }}
left join
    {{ ref("int_powerschool__gpa_term") }} as gpa
    on co.studentid = gpa.studentid
    and co.yearid = gpa.yearid
    and gpa.is_current
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
left join intervention_rosters as tr on co.student_number = tr.student_school_id
left join
    att_reconciliation_rollup as ar
    on co.student_number = ar.student_number
    and co.schoolid = ar.schoolid
left join
    suspension_reconciliation_rollup as sr
    on co.student_number = sr.student_number
    and dli.incident_id = sr.incident_id
    and co.schoolid = sr.schoolid
    and sr.rn_incident = 1
where
    co.academic_year >= {{ var("current_academic_year") - 1 }} and co.grade_level != 99
