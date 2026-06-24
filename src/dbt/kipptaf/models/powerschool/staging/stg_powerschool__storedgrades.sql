with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__storedgrades"),
                    source("kippcamden_powerschool", "stg_powerschool__storedgrades"),
                    source("kippmiami_powerschool", "stg_powerschool__storedgrades"),
                    source(
                        "kipppaterson_powerschool", "stg_powerschool__storedgrades"
                    ),
                ]
            )
        }}
    )

select
    u.*,

    case
        when u.credit_type like 'ENG%'
        then 'ENG'
        when u.credit_type like 'MATH%'
        then 'MATH'
        when u.credit_type like 'SCI%'
        then 'SCI'
        when u.credit_type like 'SOC%'
        then 'SOC'
        else u.credit_type
    end as agg_credittype,

    if(l.location_name is null, true, false) as is_transfer_grade,

    {{ extract_code_location("u") }} as _dbt_source_project,

from union_relations as u
left join
    {{ ref("int_people__location_crosswalk") }} as l on u.schoolname = l.location_name
