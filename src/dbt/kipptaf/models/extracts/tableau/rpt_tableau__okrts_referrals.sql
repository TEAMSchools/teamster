with
    ssds_period as (
        select
            'SSDS Reporting Period 1' as ssds_period,

            {{ var("current_academic_year") }} as academic_year,

            date({{ var("current_academic_year") }}, 9, 1) as period_start_date,
            date({{ var("current_academic_year") }}, 12, 31) as period_end_date,

        union all

        select
            'SSDS Reporting Period 1' as ssds_period,

            {{ var("current_academic_year") - 1 }} as academic_year,

            date({{ var("current_academic_year") - 1 }}, 9, 1) as period_start_date,
            date({{ var("current_academic_year") - 1 }}, 12, 31) as period_end_date,

        union all

        select
            'SSDS Reporting Period 2' as ssds_period,

            {{ var("current_academic_year") }} as academic_year,

            date({{ var("current_academic_year") }} + 1, 1, 1) as period_start_date,
            date({{ var("current_academic_year") }} + 1, 6, 30) as period_end_date,

        union all

        select
            'SSDS Reporting Period 2' as ssds_period,

            {{ var("current_academic_year") - 1 }} as academic_year,

            date({{ var("current_academic_year") }}, 1, 1) as period_start_date,
            date({{ var("current_academic_year") }}, 6, 30) as period_end_date,
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
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
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
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
            on rs.school_name = lc.name
    ),

    attachments as (
        select
            incident_id,

            'Suspension Letter' as incident_type,

            string_agg(
                concat(entity_name, ' (', cast(file_posted_at__date as date), ')'), '; '
            ) as attachments,
        from {{ ref("int_deanslist__incidents__attachments") }}
        where
            entity_name in (
                'KIPP Miami Suspension Letter',
                'Short-Term OSS (no further investigation)',
                'OSS Long-Term Suspension',
                'OSS Suspended Next Day'
            )
        group by incident_id

        union all

        select
            incident_id,

            'Upload' as incident_type,

            string_agg(
                concat(public_filename, ' (', cast(file_posted_at__date as date), ')'),
                '; '
            ) as attachments,
        from {{ ref("int_deanslist__incidents__attachments") }}
        where attachment_type = 'UPLOAD'
        group by incident_id
    )

select
    co.student_number,
    co.state_studentnumber,
    co.student_name,
    co.academic_year,
    co.schoolid,
    co.school,
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
    co.ms_attended,
    co.team as homeroom_section,
    co.advisor_lastfirst as homeroom_teacher_name,
    co.unweighted_ada as ada,
    co.absences_unexcused_year as days_absent_unexcused,
    co.iep_status,
    co.ml_status,
    co.status_504,
    co.self_contained_status,
    co.week_start_monday,
    co.week_end_sunday,
    co.date_count as days_in_session,
    co.quarter as term,

    dli.incident_id,
    dli.create_ts_date,
    dli.return_date_date as return_date,
    dli.category,
    dli.reported_details,
    dli.admin_summary,
    dli.infraction as incident_type,
    dli.approver_lastfirst as hi_approver_name,
    dli.nj_state_reporting,
    dli.restraint_used,
    dli.restraint_duration,
    dli.restraint_type,
    dli.ssds_incident_id,
    dli.referral_to_law_enforcement,
    dli.arrested_for_school_related_activity,
    dli.final_approval,
    dli.board_approval_date,
    dli.hi_start_date,
    dli.hi_end_date,
    dli.hours_per_week,
    dli.incident_penalty_id,
    dli.num_days,
    dli.is_suspension,
    dli.penalty_name,
    dli.start_date,
    dli.end_date,
    dli.create_lastfirst as entry_staff,
    dli.update_lastfirst as last_update_staff,
    dli.suspension_type,

    gpa.gpa_y1,

    ar.att_discrepancy_count,

    ats.attachments,
    atr.attachments as attachments_uploaded,

    coalesce(s.ssds_period, 'Outside SSDS Period') as ssds_period,

    if(co.unweighted_ada <= 0.90, true, false) as is_chronically_absent,

    if(sr.incident_id is not null, true, false) as is_discrepant_incident,

    if(tr.student_school_id is not null, true, false) as is_tier3_4,

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

    count(distinct co.student_number) over (
        partition by co.week_start_monday, co.schoolid
    ) as school_enrollment_by_week,

    max(if(dli.is_suspension, 1, 0)) over (
        partition by co.academic_year, co.student_number
    ) as is_suspended_y1_int,

    max(if(dli.suspension_type = 'OSS', 1, 0)) over (
        partition by co.academic_year, co.student_number
    ) as is_suspended_y1_oss_int,

    max(if(dli.suspension_type = 'ISS', 1, 0)) over (
        partition by co.academic_year, co.student_number
    ) as is_suspended_y1_iss_int,

    row_number() over (
        partition by co.academic_year, co.student_number
        order by co.week_start_monday asc
    ) as rn_student_year,

    if(
        sum(if(dli.is_suspension, 1, 0)) over (
            partition by co.academic_year, co.student_number
        )
        = 1,
        1,
        0
    ) as is_suspended_y1_one_int,

    if(
        sum(if(dli.suspension_type = 'OSS', 1, 0)) over (
            partition by co.academic_year, co.student_number
        )
        = 1,
        1,
        0
    ) as is_suspended_y1_oss_one_int,

    if(
        sum(if(dli.suspension_type = 'ISS', 1, 0)) over (
            partition by co.academic_year, co.student_number
        )
        = 1,
        1,
        0
    ) as is_suspended_y1_iss_one_int,

    if(
        sum(if(dli.is_suspension, 1, 0)) over (
            partition by co.academic_year, co.student_number
        )
        > 1,
        1,
        0
    ) as is_suspended_y1_2plus_int,

    if(
        sum(if(dli.suspension_type = 'OSS', 1, 0)) over (
            partition by co.academic_year, co.student_number
        )
        > 1,
        1,
        0
    ) as is_suspended_y1_oss_2plus_int,

    if(
        sum(if(dli.suspension_type = 'ISS', 1, 0)) over (
            partition by co.academic_year, co.student_number
        )
        > 1,
        1,
        0
    ) as is_suspended_y1_iss_2plus_int,

    if(
        dli.incident_id is null,
        null,
        row_number() over (
            partition by co.academic_year, co.student_number, dli.incident_id
            order by dli.is_suspension desc
        )
    ) as rn_incident,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
left join
    {{ ref("int_deanslist__incidents__penalties") }} as dli
    on co.student_number = dli.student_school_id
    and co.academic_year = dli.create_ts_academic_year
    and extract(date from dli.create_ts_date)
    between co.week_start_monday and co.week_end_sunday
    and {{ union_dataset_join_clause(left_alias="co", right_alias="dli") }}
left join
    ssds_period as s
    on dli.create_ts_date between s.period_start_date and s.period_end_date
left join
    {{ ref("int_powerschool__gpa_term") }} as gpa
    on co.studentid = gpa.studentid
    and co.yearid = gpa.yearid
    and gpa.is_current
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
left join
    {{ ref("int_deanslist__roster_assignments") }} as tr
    on co.student_number = tr.student_school_id
    and tr.roster_name = 'Tier 3/Tier 4 Intervention'
left join
    att_reconciliation_rollup as ar
    on co.student_number = ar.student_number
    and co.schoolid = ar.schoolid
    and s.ssds_period = ar.ssds_period
    and co.academic_year = ar.academic_year
left join
    suspension_reconciliation_rollup as sr
    on co.student_number = sr.student_number
    and co.schoolid = sr.schoolid
    and dli.incident_id = sr.incident_id
    and sr.rn_incident = 1
left join
    attachments as ats
    on dli.incident_id = ats.incident_id
    and ats.incident_type = 'Suspension Letter'
left join
    attachments as atr
    on dli.incident_id = atr.incident_id
    and atr.incident_type = 'Upload'
where co.academic_year >= {{ var("current_academic_year") - 1 }}
