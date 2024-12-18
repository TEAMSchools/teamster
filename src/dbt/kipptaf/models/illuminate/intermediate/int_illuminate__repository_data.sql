{{- config(materialized="view") -}}

{% set relations = dbt_utils.get_relations_by_prefix(
    schema=generate_schema_name("illuminate"),
    prefix="stg_illuminate__dna_repositories__repository_",
    exclude="stg_illuminate__dna_repositories__repository_%s",
) %}

with
    union_relations as (
        {% for relation in relations %}
            select repository_id, repository_row_id, student_id, field_name, `value`,
            from {{ relation }}
            {% if not loop.last %}
                union all
            {% endif %}
        {% endfor %}
    )

select
    ur.repository_id,
    ur.repository_row_id,
    ur.student_id,
    ur.field_name,
    ur.value,

    r.title,
    r.scope,
    r.subject_area,
    r.date_administered,

    rf.label as field_label,

    s.local_student_id,
from union_relations as ur
inner join
    {{ ref("int_illuminate__repositories") }} as r on ur.repository_id = r.repository_id
inner join
    {{ ref("stg_illuminate__dna_repositories__repository_fields") }} as rf
    on ur.repository_id = rf.repository_id
    and ur.field_name = rf.name
inner join
    {{ ref("stg_illuminate__public__students") }} as s on ur.student_id = s.student_id
