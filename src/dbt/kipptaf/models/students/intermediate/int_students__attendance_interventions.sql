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
                    'Chronic Absence: 8',
                    'Chronic Absence: 10',
                    'Chronic Absence: 15+'
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

    comm_log as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_deanslist__comm_log"),
                partition_by="student_school_id, academic_year, reason",
                order_by="call_date desc",
            )
        }}
    ),

    schoolid_crosswalk as (
        /* DL school ID not unique, need a better crosswalk */
        select distinct powerschool_school_id, deanslist_school_id,
        from {{ ref("stg_google_sheets__people__location_crosswalk") }}
        where deanslist_school_id is not null and powerschool_school_id is not null
    )

select
    ada._dbt_source_relation,
    ada.student_number,
    ada.academic_year,
    ada.days_absent_unexcused,

    sc.commlog_reason,
    sc.absence_threshold,

    c.response as commlog_notes,
    c.topic as commlog_topic,
    c.call_date as commlog_date,
    c.call_status as commlog_status,
    c.call_type as commlog_type,
    c.user_full_name as commlog_staff_name,

    lc.powerschool_school_id as schoolid,

    if(c.reason is not null, 'Complete', 'Missing') as intervention_status,
    if(c.reason is not null, 1, 0) as intervention_status_required_int,
from {{ ref("int_powerschool__ada") }} as ada
inner join
    intervention_scaffold as sc
    on {{ union_dataset_join_clause(left_alias="ada", right_alias="sc") }}
    and ada.days_absent_unexcused >= sc.absence_threshold
left join
    comm_log as c
    on ada.student_number = c.student_school_id
    and ada.academic_year = c.academic_year
    and (c.call_status = 'Completed' or c.call_type = 'IP')
    and {{ union_dataset_join_clause(left_alias="ada", right_alias="c") }}
    and sc.commlog_reason = c.reason
    and {{ union_dataset_join_clause(left_alias="sc", right_alias="c") }}
left join schoolid_crosswalk as lc on c.dl_school_id = lc.deanslist_school_id
