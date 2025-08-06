with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "base_powerschool__sections"),
                    source("kippcamden_powerschool", "base_powerschool__sections"),
                    source("kippmiami_powerschool", "base_powerschool__sections"),
                ]
            )
        }}
    )

select ur.*, if(cx.ap_course_subject is not null, true, false) as is_ap_course,
from union_relations as ur
left join
    {{ ref("stg_powerschool__s_nj_crs_x") }} as cx
    on ur.courses_dcid = cx.coursesdcid
    and {{ union_dataset_join_clause(left_alias="ur", right_alias="cx") }}
