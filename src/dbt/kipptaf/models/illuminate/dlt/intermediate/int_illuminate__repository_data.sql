with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_illuminate__dna_repositories__repository_426"),
                    ref("stg_illuminate__dna_repositories__repository_427"),
                    ref("stg_illuminate__dna_repositories__repository_429"),
                    ref("stg_illuminate__dna_repositories__repository_430"),
                    ref("stg_illuminate__dna_repositories__repository_431"),
                    ref("stg_illuminate__dna_repositories__repository_432"),
                    ref("stg_illuminate__dna_repositories__repository_433"),
                    ref("stg_illuminate__dna_repositories__repository_434"),
                    ref("stg_illuminate__dna_repositories__repository_435"),
                    ref("stg_illuminate__dna_repositories__repository_436"),
                    ref("stg_illuminate__dna_repositories__repository_437"),
                    ref("stg_illuminate__dna_repositories__repository_438"),
                    ref("stg_illuminate__dna_repositories__repository_439"),
                    ref("stg_illuminate__dna_repositories__repository_440"),
                    ref("stg_illuminate__dna_repositories__repository_441"),
                    ref("stg_illuminate__dna_repositories__repository_442"),
                    ref("stg_illuminate__dna_repositories__repository_443"),
                    ref("stg_illuminate__dna_repositories__repository_444"),
                    ref("stg_illuminate__dna_repositories__repository_445"),
                    ref("stg_illuminate__dna_repositories__repository_446"),
                    ref("stg_illuminate__dna_repositories__repository_447"),
                    ref("stg_illuminate__dna_repositories__repository_448"),
                    ref("stg_illuminate__dna_repositories__repository_449"),
                    ref("stg_illuminate__dna_repositories__repository_450"),
                    ref("stg_illuminate__dna_repositories__repository_451"),
                    ref("stg_illuminate__dna_repositories__repository_452"),
                    ref("stg_illuminate__dna_repositories__repository_453"),
                    ref("stg_illuminate__dna_repositories__repository_454"),
                    ref("stg_illuminate__dna_repositories__repository_455"),
                    ref("stg_illuminate__dna_repositories__repository_456"),
                    ref("stg_illuminate__dna_repositories__repository_457"),
                    ref("stg_illuminate__dna_repositories__repository_458"),
                    ref("stg_illuminate__dna_repositories__repository_459"),
                    ref("stg_illuminate__dna_repositories__repository_460"),
                    ref("stg_illuminate__dna_repositories__repository_461"),
                    ref("stg_illuminate__dna_repositories__repository_462"),
                    ref("stg_illuminate__dna_repositories__repository_463"),
                    ref("stg_illuminate__dna_repositories__repository_464"),
                    ref("stg_illuminate__dna_repositories__repository_465"),
                    ref("stg_illuminate__dna_repositories__repository_466"),
                    ref("stg_illuminate__dna_repositories__repository_467"),
                    ref("stg_illuminate__dna_repositories__repository_468"),
                    ref("stg_illuminate__dna_repositories__repository_469"),
                    ref("stg_illuminate__dna_repositories__repository_470"),
                    ref("stg_illuminate__dna_repositories__repository_471"),
                    ref("stg_illuminate__dna_repositories__repository_472"),
                ]
            )
        }}
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
