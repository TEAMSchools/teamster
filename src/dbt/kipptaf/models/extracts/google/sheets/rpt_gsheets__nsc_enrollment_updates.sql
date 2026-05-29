with
    /* Each existing kippadb enrollment matches the latest overlapping NSC
       stint at the same (student, school). When several stints overlap one
       enrollment, the most recent stint carries the freshest status. */
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    enrollment_stint_match as (
        select
            e.id as enrollment_id,
            e.actual_end_date,
            e.attending_status,
            e.`status`,
            e.do_not_overwrite_with_nsc_data,

            n.stint_num,
            n.stint_end,
            n.current_enrollment_status,
            n.derived_status,
        from {{ ref("stg_kippadb__enrollment") }} as e
        inner join
            {{ ref("int_nsc__enrollment_stints") }} as n
            on e.student = n.contact_id
            and e.school = n.account_id
            and coalesce(e.actual_end_date, date(9999, 12, 31)) >= n.stint_begin
            and e.`start_date` <= n.stint_end
    ),

    enrollment_latest_stint as (
        {{
            dbt_utils.deduplicate(
                relation="enrollment_stint_match",
                partition_by="enrollment_id",
                order_by="stint_end desc, stint_num desc",
            )
        }}
    )

select
    enrollment_id as id,
    stint_end as actual_end_date__c,
    derived_status as status__c,
    current_enrollment_status as attending_status__c,

    true as nsc_verified__c,
    current_date('{{ var("local_timezone") }}') as date_last_verified__c,
from enrollment_latest_stint
where
    not do_not_overwrite_with_nsc_data
    and (
        stint_end is distinct from actual_end_date
        or derived_status is distinct from `status`
        or current_enrollment_status is distinct from attending_status
    )
