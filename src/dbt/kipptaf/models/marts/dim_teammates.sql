with
    roster as (select *, from {{ ref("int_people__staff_roster_history") }}),

    final as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    ["employee_number", "effective_date_start"]
                )
            }} as employee_key,
            roster.*,
            if(
                primary_indicator and (is_current_record or is_prestart), true, false
            ) as current_roster,
            if(
                job_title in (
                    'Teacher',
                    'Teacher in Residence',
                    'ESE Teacher',
                    'Learning Specialist',
                    'Teacher ESL',
                    'Teacher in Residence ESL'
                ),
                true,
                false
            ) as is_teacher,

        from roster
    )

select *
from final
