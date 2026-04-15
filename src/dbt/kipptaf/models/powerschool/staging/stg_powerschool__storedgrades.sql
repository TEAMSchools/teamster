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

    if(l.name is null, true, false) as is_transfer_grade,

from union_relations as u
left join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as l
    on u.schoolname = l.name
