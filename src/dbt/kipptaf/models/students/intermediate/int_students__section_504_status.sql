select
    s.student_number,
    s._dbt_source_project,

    njs.is_504 as is_504_state_field,

    if(ap.student_number is not null, true, false) as has_active_edplan_504_plan,
from {{ ref("stg_powerschool__students") }} as s
left join
    {{ ref("stg_powerschool__s_nj_stu_x") }} as njs
    on s.dcid = njs.studentsdcid
    and s._dbt_source_project = njs._dbt_source_project
left join
    {{ ref("int_edplan__section_504_active_plan_rollup") }} as ap
    on s.student_number = ap.student_number
    and s._dbt_source_project = ap._dbt_source_project
where s.dcid >= 1
