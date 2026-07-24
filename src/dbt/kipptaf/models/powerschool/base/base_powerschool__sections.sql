with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "base_powerschool__sections"),
                    source("kippcamden_powerschool", "base_powerschool__sections"),
                    source("kippmiami_powerschool", "base_powerschool__sections"),
                    source("kipppaterson_powerschool", "base_powerschool__sections"),
                ]
            )
        }}
    ),

    sections as (
        select *, {{ extract_source_project() }} as _dbt_source_project,
        from union_relations
    )

select sec.*, if(cx.ap_course_subject is not null, true, false) as is_ap_course,
from sections as sec
left join
    {{ ref("stg_powerschool__s_nj_crs_x") }} as cx
    on sec.courses_dcid = cx.coursesdcid
    and sec._dbt_source_project = cx._dbt_source_project
