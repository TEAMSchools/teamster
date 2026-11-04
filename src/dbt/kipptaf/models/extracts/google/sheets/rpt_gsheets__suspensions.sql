with
    suspensions as (
        select
            _dbt_source_project,
            incident_id,
            incident_penalty_id,
            student_school_id,
            create_ts_academic_year,
            create_lastfirst as entry_staff,
            referral_tier,
            category,
            admin_summary,
            reported_details,
            nj_state_reporting,
            ssds_incident_id,
            penalty_name,
            suspension_type,
            start_date,
            end_date,
            num_days,

            date(create_ts_date) as created_date,
        from {{ ref("int_deanslist__incidents__penalties") }}
        where
            is_suspension
            and create_ts_academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    enrollment_picks as (
        select
            s.incident_penalty_id,
            s._dbt_source_project,
            s.student_school_id,
            s.create_ts_academic_year,

            coalesce(ed.entrydate, ey.entrydate) as entrydate,
        from suspensions as s
        left join
            {{ ref("int_extracts__student_enrollments") }} as ed
            on s.student_school_id = ed.student_number
            and s.create_ts_academic_year = ed.academic_year
            and s._dbt_source_project = ed._dbt_source_project
            and s.created_date >= ed.entrydate
            and s.created_date <= ed.last_enrolled_date
        left join
            {{ ref("int_extracts__student_enrollments") }} as ey
            on s.student_school_id = ey.student_number
            and s.create_ts_academic_year = ey.academic_year
            and s._dbt_source_project = ey._dbt_source_project
            and ey.rn_year = 1
    ),

    attachments as (
        select
            incident_id,
            _dbt_source_project,
            file_posted_at__date,

            coalesce(entity_name, public_filename) as attachment_name,
            format_datetime('%F', file_posted_at__date) as posted_date,

            -- same suspension letter templates as rpt_tableau__okrts_referrals
            attachment_type = 'INC-LETTER'
            and coalesce(
                entity_name in (
                    'KIPP Miami Suspension Letter',
                    'Short-Term OSS (no further investigation)',
                    'OSS Long-Term Suspension',
                    'OSS Suspended Next Day',
                    'OSS',
                    'OSS Suspension Letter (pending further investigation)',
                    'ISS Suspension Letter'
                ),
                false
            ) as is_suspension_letter,
        from {{ ref("int_deanslist__incidents__attachments") }}
    ),

    attachment_labels as (
        select
            incident_id,
            _dbt_source_project,
            file_posted_at__date,
            is_suspension_letter,

            concat(attachment_name, ' (', posted_date, ')') as attachment_label,
        from attachments
    ),

    attachment_rollup as (
        select
            incident_id,
            _dbt_source_project,

            string_agg(
                if(is_suspension_letter, attachment_label, null),
                '; '
                order by file_posted_at__date
            ) as suspension_letters,

            string_agg(
                if(is_suspension_letter, null, attachment_label),
                '; '
                order by file_posted_at__date
            ) as other_attachments,
        from attachment_labels
        group by incident_id, _dbt_source_project
    )

select
    e.region,
    e.school,
    e.academic_year_display as academic_year,
    e.student_number,
    e.student_name,
    e.grade_level,
    e.gender,
    e.team as homeroom_section,
    e.iep_status,
    e.ml_status,

    s.incident_id,
    s.created_date,
    s.entry_staff,
    s.referral_tier,
    s.category,
    s.admin_summary,
    s.reported_details,
    s.nj_state_reporting,
    s.ssds_incident_id,
    s.incident_penalty_id,
    s.penalty_name,
    s.suspension_type,
    s.start_date,
    s.end_date,
    s.num_days,

    ar.suspension_letters,
    ar.other_attachments,
from {{ ref("int_extracts__student_enrollments") }} as e
-- Miami DeansList ids match no Focus student number until #5790, so those drop here
inner join
    enrollment_picks as ep
    on e.student_number = ep.student_school_id
    and e.academic_year = ep.create_ts_academic_year
    and e._dbt_source_project = ep._dbt_source_project
    and e.entrydate = ep.entrydate
inner join
    suspensions as s
    on ep.incident_penalty_id = s.incident_penalty_id
    and ep._dbt_source_project = s._dbt_source_project
left join
    attachment_rollup as ar
    on s.incident_id = ar.incident_id
    and s._dbt_source_project = ar._dbt_source_project
