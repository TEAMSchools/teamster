with
    intervention_scaffold as (
        select
            'kippmiami' as code_location,
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
                    'Chronic Absence: 20+'
                ]
            ) as commlog_reason

        union all

        select
            code_location,
            commlog_reason,
            safe_cast(
                regexp_extract(commlog_reason, r'(\d+)') as int64
            ) as absence_threshold,
        from
            unnest(
                [
                    'Chronic Absence: 4',
                    'Chronic Absence: 8',
                    'Chronic Absence: 12',
                    'Chronic Absence: 16',
                    'Chronic Absence: 20',
                    'Chronic Absence: 30',
                    'Chronic Absence: 40'
                ]
            ) as commlog_reason
        cross join unnest(['kippnewark', 'kippcamden']) as code_location
    ),

    ada_calc as (
        select
            _dbt_source_relation,
            studentid,
            days_absent_unexcused,

            yearid + 1990 as academic_year,
            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as code_location,
        from {{ ref("int_powerschool__ada") }}
    ),

    commlog_raw as (
        select
            c.student_school_id as student_number,
            c.reason as commlog_reason,
            c.response as commlog_notes,
            c.topic as commlog_topic,
            c.call_status as commlog_status,
            c.call_type as commlog_type,
            c._dbt_source_relation,

            {{
                date_to_fiscal_year(
                    date_field="c.call_date_time", start_month=7, year_source="start"
                )
            }} as academic_year,
            safe_cast(c.call_date_time as date) as commlog_date,
            concat(u.first_name, ' ', u.last_name) as commlog_staff_name,
        from {{ ref("stg_deanslist__comm_log") }} as c
        inner join
            {{ ref("stg_deanslist__users") }} as u
            on c.user_id = u.dl_user_id
            and {{ union_dataset_join_clause(left_alias="c", right_alias="u") }}
    ),

    commlog as (
        select
            *,

            row_number() over (
                partition by student_number, commlog_reason, academic_year
                order by commlog_date desc
            ) as rn_commlog_reason,
        from commlog_raw
    )

select
    sc.code_location,
    sc.commlog_reason,
    sc.absence_threshold,

    ada.days_absent_unexcused,
    ada.academic_year,

    s.student_number,

    c.commlog_staff_name,
    c.commlog_notes,
    c.commlog_topic,
    c.commlog_date,
    c.commlog_status,
    c.commlog_type,

    /* CASE statement used here instead of IF in order to maintain NULLs */
    case
        when c.commlog_reason is not null
        then 'Complete'
        when
            ada.days_absent_unexcused >= sc.absence_threshold
            and c.commlog_reason is null
        then 'Missing'
    end as intervention_status,
    case
        when
            ada.days_absent_unexcused >= sc.absence_threshold
            and c.commlog_reason is null
        then 0
        when
            ada.days_absent_unexcused >= sc.absence_threshold
            and c.commlog_reason is not null
        then 1
    end as intervention_status_required_int,
from intervention_scaffold as sc
inner join ada_calc as ada on sc.code_location = ada.code_location
inner join
    {{ ref("stg_powerschool__students") }} as s
    on ada.studentid = s.id
    and {{ union_dataset_join_clause(left_alias="ada", right_alias="s") }}
left join
    commlog as c
    on s.student_number = c.student_number
    and ada.academic_year = c.academic_year
    and sc.commlog_reason = c.commlog_reason
    and c.rn_commlog_reason = 1
where ada.days_absent_unexcused >= sc.absence_threshold
