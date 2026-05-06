with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "int_deanslist__incidents"),
                    source("kippcamden_deanslist", "int_deanslist__incidents"),
                    source("kippmiami_deanslist", "int_deanslist__incidents"),
                ]
            )
        }}
    ),

    sanitized as (
        -- trunk-ignore(sqlfluff/AM04): union_relations expands at compile time
        select
            * except (close_ts_date),

            if(
                close_ts_date < datetime '2000-01-01', null, close_ts_date
            ) as close_ts_date,
        from union_relations
    )

select u.*, {{ extract_code_location("u") }} as _dbt_source_project, loc.location_key,
from sanitized as u
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on u.school_id = loc.deanslist_school_id
    and not loc.is_pathways
    and loc.location_name <> 'KIPP Whittier Elementary'
