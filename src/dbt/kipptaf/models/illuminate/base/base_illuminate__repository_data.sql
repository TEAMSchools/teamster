{{ config(materialized="view") }}

{%- set relations = dbt_utils.get_relations_by_prefix(
    schema=model.schema,
    prefix="stg_illuminate__repository_",
    exclude="stg_illuminate__repository_%s",
) -%}

with union_relations as ({{ dbt_utils.union_relations(relations=relations) }})

select
    ur.*,

    r.title,
    r.scope,
    r.subject_area,
    r.administered_at,

    s.local_student_id,

    rf.label as field_label,
from union_relations as ur
inner join
    {{ ref("base_illuminate__repositories") }} as r
    on ur.repository_id = r.repository_id
inner join {{ ref("stg_illuminate__students") }} as s on ur.student_id = s.student_id
inner join
    {{ ref("stg_illuminate__repository_fields") }} as rf
    on ur.repository_id = rf.repository_id
    and ur.field_name = rf.name
