with
    encoded as (
        select staff_id, cast(active as string) as custom_319000004,
        from {{ ref("stg_focus__users") }}
    ),

    unpivoted as (
        select staff_id, column_name, stored_value,
        from encoded unpivot (stored_value for column_name in (custom_319000004))
    ),

    decoded as (
        select unpivoted.staff_id, unpivoted.column_name, `options`.label,
        from unpivoted
        left join
            {{ ref("int_focus__custom_field_options") }} as `options`
            on unpivoted.column_name = `options`.column_name
            and unpivoted.stored_value in (`options`.option_id, `options`.code)
            and `options`.source_class = 'FocusUser'
    ),

    select_pivot as (
        select *,
        from
            decoded pivot (
                any_value(label) for column_name in ('custom_319000004' as active_label)
            )
    ),

    -- multiple: education is a JSON array of option ids like '["2795"]'; explode,
    -- map each id to its label, re-aggregate. CTE form avoids a correlated subquery.
    education as (
        select
            users.staff_id,
            array_agg(
                `options`.label ignore nulls order by `options`.label
            ) as education_label,
        from {{ ref("stg_focus__users") }} as users
        cross join unnest(json_value_array(users.education)) as element_id
        left join
            {{ ref("int_focus__custom_field_options") }} as `options`
            on element_id in (`options`.option_id, `options`.code)
            and `options`.column_name = 'custom_2'
            and `options`.source_class = 'FocusUser'
        group by users.staff_id
    )

select users.staff_id, select_pivot.active_label, education.education_label,
from {{ ref("stg_focus__users") }} as users
left join select_pivot on users.staff_id = select_pivot.staff_id
left join education on users.staff_id = education.staff_id
