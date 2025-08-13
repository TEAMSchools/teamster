with
    intervention_scaffold as (
        select
            'kippmiami_deanslist' as _dbt_source_relation,

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
            _dbt_source_relation,
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
        cross join
            unnest(
                ['kippnewark_deanslist', 'kippcamden_deanslist']
            ) as _dbt_source_relation
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
    ada._dbt_source_relation,
    ada.student_number,
    ada.academic_year,
    ada.days_absent_unexcused,

    sc.commlog_reason,
    sc.absence_threshold,

    c.user_name as commlog_staff_name,
    c.commlog_notes,
    c.commlog_topic,
    c.call_date as commlog_date,
    c.commlog_status,
    c.commlog_type,

    if(c.commlog_reason is not null, 'Complete', 'Missing') as intervention_status,
    if(c.commlog_reason is not null, 1, 0) as intervention_status_required_int,
from {{ ref("int_powerschool__ada") }} as ada
inner join
    intervention_scaffold as sc
    on {{ union_dataset_join_clause(left_alias="ada", right_alias="sc") }}
    and ada.days_absent_unexcused >= sc.absence_threshold
left join
    commlog as c
    on ada.student_number = c.student_number
    and ada.academic_year = c.academic_year
    and {{ union_dataset_join_clause(left_alias="ada", right_alias="c") }}
    and sc.commlog_reason = c.commlog_reason
    and {{ union_dataset_join_clause(left_alias="sc", right_alias="c") }}
    and c.rn_commlog_reason = 1
