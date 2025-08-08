with
    intervention_scaffold as (
        select
            'kippmiami' as _dbt_source_project,

            commlog_reason,

            safe_cast(
                regexp_extract(commlog_reason, r'(\d+)') as int
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
            _dbt_source_project,
            commlog_reason,

            safe_cast(
                regexp_extract(commlog_reason, r'(\d+)') as int
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
        cross join unnest(['kippnewark', 'kippcamden']) as _dbt_source_project
    ),

    commlog as (
        select
            c._dbt_source_relation,
            c.student_school_id as student_number,
            c.academic_year,
            c.reason as commlog_reason,
            c.response as commlog_notes,
            c.topic as commlog_topic,
            c.call_status as commlog_status,
            c.call_type as commlog_type,
            c.call_date,

            u.user_name,

            row_number() over (
                partition by c.student_school_id, c.reason, c.academic_year
                order by c.call_date desc
            ) as rn_commlog_reason,
        from {{ ref("stg_deanslist__comm_log") }} as c
        inner join
            {{ ref("stg_deanslist__users") }} as u
            on c.user_id = u.dl_user_id
            and {{ union_dataset_join_clause(left_alias="c", right_alias="u") }}
    )

select
    sc._dbt_source_project,
    sc.commlog_reason,
    sc.absence_threshold,

    ada.days_absent_unexcused,
    ada.academic_year,

    s.student_number,

    c.user_name as commlog_staff_name,
    c.commlog_notes,
    c.commlog_topic,
    c.call_date as commlog_date,
    c.commlog_status,
    c.commlog_type,

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
inner join
    {{ ref("int_powerschool__ada") }} as ada
    on sc._dbt_source_project = ada._dbt_source_project
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
