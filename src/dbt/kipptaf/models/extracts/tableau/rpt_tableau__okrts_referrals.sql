with
    ssds_period_definitions as (
        select
            'SSDS Reporting Period 1' as ssds_period,
            0 as year_offset,
            0 as start_year_delta,
            9 as start_month,
            1 as start_day,
            0 as end_year_delta,
            12 as end_month,
            31 as end_day
        union all
        select 'SSDS Reporting Period 1', -1, 0, 9, 1, 0, 12, 31
        union all
        select 'SSDS Reporting Period 2', 0, 1, 1, 1, 1, 6, 30
        union all
        select 'SSDS Reporting Period 2', -1, 1, 1, 1, 1, 6, 30
    ),

    ssds_period as (
        select
            ssds_period,
            {{ var("current_academic_year") }} + year_offset as academic_year,
            date(
                {{ var("current_academic_year") }} + year_offset + start_year_delta,
                start_month,
                start_day
            ) as period_start_date,
            date(
                {{ var("current_academic_year") }} + year_offset + end_year_delta,
                end_month,
                end_day
            ) as period_end_date,
        from ssds_period_definitions
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

            string_agg(
                if(
                    entity_name in (
                        'KIPP Miami Suspension Letter',
                        'Short-Term OSS (no further investigation)',
                        'OSS Long-Term Suspension',
                        'OSS Suspended Next Day',
                        'OSS',
                        'OSS Suspension Letter (pending further investigation)',
                        'ISS Suspension Letter'
                    ),
                    concat(entity_name, ' (', cast(file_posted_at__date as date), ')'),
                    null
                ),
                '; '
            ) as suspension_letter_attachments,

            string_agg(
                if(
                    attachment_type = 'UPLOAD',
                    concat(
                        public_filename, ' (', cast(file_posted_at__date as date), ')'
                    ),
                    null
                ),
                '; '
            ) as uploaded_attachments,
        from {{ ref("int_deanslist__incidents__attachments") }}
        where
            entity_name in (
                'KIPP Miami Suspension Letter',
                'Short-Term OSS (no further investigation)',
                'OSS Long-Term Suspension',
                'OSS Suspended Next Day',
                'OSS',
                'OSS Suspension Letter (pending further investigation)',
                'ISS Suspension Letter'
            )
            or attachment_type = 'UPLOAD'
        group by incident_id
    ),

    base as (
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

            at.suspension_letter_attachments as attachments,
            at.uploaded_attachments as attachments_uploaded,

            coalesce(s.ssds_period, 'Outside SSDS Period') as ssds_period,

            coalesce(co.unweighted_ada <= 0.90, false) as is_chronically_absent,

            sr.incident_id is not null as is_discrepant_incident,

            tr.student_school_id is not null as is_tier3_4,

            case
                when
                    left(dli.category, 2) in ('SW', 'SS')
                    or left(dli.category, 3) in ('SSC', 'SSW')
                then 'Social Work'
                when (left(dli.category, 2) = 'TX' or dli.category like 'Documentation%')
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

            row_number() over (
                partition by co.academic_year, co.student_number
                order by co.week_start_monday asc
            ) as rn_student_year,

            if(
                dli.incident_id is null,
                null,
                row_number() over (
                    partition by co.academic_year, co.student_number, dli.incident_id
                    order by dli.is_suspension desc
                )
            ) as rn_incident,

            sum(if(dli.is_suspension, 1, 0)) over (
                partition by co.academic_year, co.student_number
            ) as sum_suspended,

            sum(if(dli.suspension_type = 'OSS', 1, 0)) over (
                partition by co.academic_year, co.student_number
            ) as sum_suspended_oss,

            sum(if(dli.suspension_type = 'ISS', 1, 0)) over (
                partition by co.academic_year, co.student_number
            ) as sum_suspended_iss,
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
        left join attachments as at on dli.incident_id = at.incident_id
        where co.academic_year >= {{ var("current_academic_year") - 1 }}
    )

select
    student_number,
    state_studentnumber,
    student_name,
    academic_year,
    schoolid,
    school,
    school_name,
    region,
    grade_level,
    enroll_status,
    cohort,
    school_level,
    gender,
    ethnicity,
    lunch_status,
    is_retained_year,
    rn_year,
    ms_attended,
    homeroom_section,
    homeroom_teacher_name,
    ada,
    days_absent_unexcused,
    iep_status,
    ml_status,
    status_504,
    self_contained_status,
    week_start_monday,
    week_end_sunday,
    days_in_session,
    term,

    incident_id,
    create_ts_date,
    return_date,
    category,
    reported_details,
    admin_summary,
    incident_type,
    hi_approver_name,
    nj_state_reporting,
    restraint_used,
    restraint_duration,
    restraint_type,
    ssds_incident_id,
    referral_to_law_enforcement,
    arrested_for_school_related_activity,
    final_approval,
    board_approval_date,
    hi_start_date,
    hi_end_date,
    hours_per_week,
    incident_penalty_id,
    num_days,
    is_suspension,
    penalty_name,
    start_date,
    end_date,
    entry_staff,
    last_update_staff,
    suspension_type,

    gpa_y1,

    att_discrepancy_count,

    attachments,
    attachments_uploaded,

    ssds_period,

    is_chronically_absent,
    is_discrepant_incident,
    is_tier3_4,

    referral_tier,

    school_enrollment_by_week,
    rn_student_year,
    rn_incident,

    if(sum_suspended > 0, 1, 0) as is_suspended_y1_int,
    if(sum_suspended_oss > 0, 1, 0) as is_suspended_y1_oss_int,
    if(sum_suspended_iss > 0, 1, 0) as is_suspended_y1_iss_int,
    if(sum_suspended = 1, 1, 0) as is_suspended_y1_one_int,
    if(sum_suspended_oss = 1, 1, 0) as is_suspended_y1_oss_one_int,
    if(sum_suspended_iss = 1, 1, 0) as is_suspended_y1_iss_one_int,
    if(sum_suspended > 1, 1, 0) as is_suspended_y1_2plus_int,
    if(sum_suspended_oss > 1, 1, 0) as is_suspended_y1_oss_2plus_int,
    if(sum_suspended_iss > 1, 1, 0) as is_suspended_y1_iss_2plus_int,
from base
