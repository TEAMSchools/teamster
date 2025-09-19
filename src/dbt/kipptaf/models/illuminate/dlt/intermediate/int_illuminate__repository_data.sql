{{ config(materialized="view") }}

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

    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_472") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_471") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_470") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_469") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_468") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_467") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_466") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_465") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_464") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_463") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_462") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_461") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_460") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_459") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_458") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_457") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_456") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_455") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_454") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_453") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_452") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_451") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_450") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_449") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_448") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_447") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_446") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_445") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_444") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_443") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_442") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_441") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_440") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_439") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_438") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_437") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_436") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_435") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_434") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_433") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_432") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_431") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_430") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_429") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_427") }}
    -- depends_on: {{ ref("stg_illuminate__dna_repositories__repository_426") -}}
    
