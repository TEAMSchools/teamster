{{ config(tags="dagster") }}

with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "adp_workforce_now",
                        "src_adp_workforce_now__person_communication",
                    ),
                    source(
                        "adp_workforce_now",
                        "src_adp_workforce_now__business_communication",
                    ),
                ],
                include=[
                    "worker_id",
                    "source_relation_type",
                    "type",
                    "email_uri",
                    "formatted_number",
                ],
            )
        }}
    ),

    source_relation_parsed as (
        select
            *,
            regexp_extract(
                _dbt_source_relation, r'(\w+)_communication'
            ) as source_relation_type,
        from union_relations
    ),

    pivot_source as (
        select
            worker_id,
            source_relation_type || '_' || `type` as input_column,
            email_uri as pivot_column
        from source_relation_parsed
        where `type` = 'email'

        union all

        select
            worker_id,
            source_relation_type || '_' || `type` as input_column,
            formatted_number as pivot_column
        from source_relation_parsed
        where `type` in ('mobile', 'landline')
    )

select *
from
    pivot_source pivot (
        max(pivot_column) for input_column in (
            'business_mobile',
            'business_landline',
            'business_email',
            'person_mobile',
            'person_landline',
            'person_email'
        )
    )
