with
    commlog as (
        select
            c.student_school_id as student_number,
            c.reason as commlog_reason,
            c.response as commlog_notes,
            c.topic as commlog_topic,
            c.call_status as commlog_status,
            c.call_type as commlog_type,
            c._dbt_source_relation,

            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="c.call_date_time", start_month=7, year_source="start"
                )
            }} as academic_year,
            safe_cast(c.call_date_time as date) as commlog_date,
            concat(u.first_name, ' ', u.last_name) as commlog_staff_name,
        from {{ ref("stg_deanslist__comm_log") }} as c
        inner join
            {{ ref("stg_deanslist__users") }} as u
            on c.user_id = u.dl_user_id
            and regexp_extract(c._dbt_source_relation, r'(kipp\w+)_')
            = regexp_extract(u._dbt_source_relation, r'(kipp\w+)_')
    ),

    commlog_reason as (
        select
            commlog_reason,
            safe_cast(
                regexp_extract(commlog_reason, r'(\d+)') as int64
            ) as absence_threshold,
        from
            unnest(
                [
                    'Chronic Absence: 3',
                    'Chronic Absence: 5',
                    'Chronic Absence: 6',
                    'Chronic Absence: 8',
                    'Chronic Absence: 10',
                    'Chronic Absence: 15+',
                    'Chronic Absence: 10+',
                    'Chronic Absence: 20+'
                ]
            ) as commlog_reason
    )

select
    co.student_number,
    co.lastfirst,
    co.grade_level,
    co.advisor_lastfirst as advisor,
    co.region,
    co.school_abbreviation as school,

    cr.commlog_reason,
    cr.absence_threshold,

    ada.days_absent_unexcused,

    c.commlog_staff_name,
    c.commlog_notes,
    c.commlog_topic,
    c.commlog_date,
    c.commlog_status,
    c.commlog_type,

    -- CASE statement used here instead of IF in order to maintain NULLs
    case
        when c.commlog_reason is not null
        then 'Complete'
        when
            ada.days_absent_unexcused >= cr.absence_threshold
            and c.commlog_reason is null
        then 'Missing'
    end as intervention_status,
    case
        when
            ada.days_absent_unexcused >= cr.absence_threshold
            and c.commlog_reason is null
        then 0
        when
            ada.days_absent_unexcused >= cr.absence_threshold
            and c.commlog_reason is not null
        then 1
    end as intervention_status_required_int,
    row_number() over (
        partition by co.academic_year, co.student_number, cr.commlog_reason
    ) as rn_commlog_reason,
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join commlog_reason as cr
left join
    {{ ref("int_powerschool__ada") }} as ada
    on co.studentid = ada.studentid
    and co.yearid = ada.yearid
    and regexp_extract(co._dbt_source_relation, r'(kipp\w+)_')
    = regexp_extract(ada._dbt_source_relation, r'(kipp\w+)_')
left join
    commlog as c
    on co.student_number = c.student_number
    and co.academic_year = c.academic_year
    and cr.commlog_reason = c.commlog_reason
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.enroll_status = 0
