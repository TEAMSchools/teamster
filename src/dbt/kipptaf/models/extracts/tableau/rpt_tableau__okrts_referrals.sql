with
    ssds_period as (
        select
            {{ var("current_academic_year") }} as academic_year,
            'SSDS Reporting Period 1' as ssds_period,
            date({{ var("current_academic_year") }}, 9, 1) as period_start_date,
            date({{ var("current_academic_year") }}, 12, 31) as period_end_date,
        union all
        select
            {{ var("current_academic_year") - 1 }} as academic_year,
            'SSDS Reporting Period 1' as ssds_period,
            date({{ var("current_academic_year") - 1 }}, 9, 1) as period_start_date,
            date({{ var("current_academic_year") - 1 }}, 12, 31) as period_end_date,
        union all
        select
            {{ var("current_academic_year") }} as academic_year,
            'SSDS Reporting Period 2' as ssds_period,
            date({{ var("current_academic_year") }} + 1, 1, 1) as period_start_date,
            date({{ var("current_academic_year") }} + 1, 6, 30) as period_end_date,
        union all
        select
            {{ var("current_academic_year") - 1 }} as academic_year,
            'SSDS Reporting Period 2' as ssds_period,
            date({{ var("current_academic_year") }}, 1, 1) as period_start_date,
            date({{ var("current_academic_year") }}, 6, 30) as period_end_date,
    ),

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

            s.academic_year,

            coalesce(s.ssds_period, 'Outside SSDS Period') as ssds_period,

            count(*) as att_discrepancy_count,
        from {{ ref("stg_deanslist__reconcile_attendance") }} as ra
        inner join
            {{ ref("stg_people__location_crosswalk") }} as lc
            on ra.school_name = lc.name
        left join
            ssds_period as s
            on ra.attendance_date between s.period_start_date and s.period_end_date
        group by ra.student_id, lc.powerschool_school_id, s.academic_year, s.ssds_period
    ),

    suspension_reconciliation_rollup as (
        select
            rs.student_id as student_number,
            rs.dl_incident_id as incident_id,
            rs.dl_penalty_id as penalty_id,

            lc.powerschool_school_id as schoolid,

            row_number() over (
                partition by rs.student_id, rs.dl_incident_id, lc.powerschool_school_id
                order by rs.consequence desc
            ) as rn_incident,
        from {{ ref("stg_deanslist__reconcile_suspensions") }} as rs
        inner join
            {{ ref("stg_people__location_crosswalk") }} as lc
            on rs.school_name = lc.name
    ),

    attachments as (
        select
            'Suspension Letter' as type,
            incident_id,
            string_agg(
                concat(entity_name, ' (', date(file_posted_at__date), ')'), '; '
            ) as attachments,
        from {{ ref("stg_deanslist__incidents__attachments") }}
        where
            entity_name in (
                'KIPP Miami Suspension Letter',
                'Short-Term OSS (no further investigation)',
                'OSS Long-Term Suspension',
                'OSS Suspended Next Day'
            )
        group by all

        union all
        select
            'Upload' as type,
            incident_id,
            string_agg(
                concat(public_filename, ' (', date(file_posted_at__date), ')'), '; '
            ) as attachments,
        from {{ ref("stg_deanslist__incidents__attachments") }}
        where attachment_type = 'UPLOAD'
        group by all
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
    dli.return_date_date as return_date,
    dli.category,
    dli.reported_details,
    dli.admin_summary,
    dli.infraction as incident_type,

    dlp.incident_penalty_id,
    dlp.num_days,
    dlp.is_suspension,
    dlp.penalty_name,
    dlp.start_date,
    dlp.end_date,

    cf.nj_state_reporting,
    cf.restraint_used,
    cf.restraint_duration,
    cf.restraint_type,
    cf.ssds_incident_id,
    cf.referral_to_law_enforcement,
    cf.arrested_for_school_related_activity,

    st.suspension_type,

    ada.days_absent_unexcused,

    gpa.gpa_y1,

    ar.att_discrepancy_count,

    ms.ms_attended,

    ats.attachments,
    atr.attachments as attachments_uploaded,

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
        when left(dli.category, 2) in ('SW', 'SS') or left(dli.category, 3) = 'SSC'
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

    if(
        sum(if(dlp.is_suspension, 1, 0)) over (
            partition by co.academic_year, co.student_number
        )
        = 1,
        1,
        0
    ) as is_suspended_y1_one_int,

    if(
        sum(if(st.suspension_type = 'OSS', 1, 0)) over (
            partition by co.academic_year, co.student_number
        )
        = 1,
        1,
        0
    ) as is_suspended_y1_oss_one_int,

    if(
        sum(if(st.suspension_type = 'ISS', 1, 0)) over (
            partition by co.academic_year, co.student_number
        )
        = 1,
        1,
        0
    ) as is_suspended_y1_iss_one_int,

    if(
        sum(if(dlp.is_suspension, 1, 0)) over (
            partition by co.academic_year, co.student_number
        )
        > 1,
        1,
        0
    ) as is_suspended_y1_2plus_int,

    if(
        sum(if(st.suspension_type = 'OSS', 1, 0)) over (
            partition by co.academic_year, co.student_number
        )
        > 1,
        1,
        0
    ) as is_suspended_y1_oss_2plus_int,

    if(
        sum(if(st.suspension_type = 'ISS', 1, 0)) over (
            partition by co.academic_year, co.student_number
        )
        > 1,
        1,
        0
    ) as is_suspended_y1_iss_2plus_int,

    if(tr.student_school_id is not null, true, false) as is_tier3_4,

    coalesce(s.ssds_period, 'Outside SSDS Period') as ssds_period,

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
    ssds_period as s
    on dli.create_ts_date between s.period_start_date and s.period_end_date
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
    and s.ssds_period = ar.ssds_period
    and co.academic_year = ar.academic_year
left join
    suspension_reconciliation_rollup as sr
    on co.student_number = sr.student_number
    and dlp.incident_id = sr.incident_id
    and co.schoolid = sr.schoolid
    and sr.rn_incident = 1
left join
    ms_grad_sub as ms
    on co.student_number = ms.student_number
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ms") }}
    and ms.rn = 1
left join
    attachments as ats
    on dli.incident_id = ats.incident_id
    and ats.type = 'Suspension Letter'
left join
    attachments as atr on dli.incident_id = atr.incident_id and atr.type = 'Upload'
where
    co.academic_year >= {{ var("current_academic_year") - 1 }} and co.grade_level != 99
