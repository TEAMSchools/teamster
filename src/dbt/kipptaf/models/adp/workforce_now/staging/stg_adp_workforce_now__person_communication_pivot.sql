{{ config(tags="dagster") }}

with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "adp_workforce_now",
                        "person_communication",
                    ),
                    source(
                        "adp_workforce_now",
                        "business_communication",
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
            email_uri as pivot_column,
            source_relation_type || '_' || `type` as input_column,
        from source_relation_parsed
        where `type` = 'email'

        union all

        select
            worker_id,
            formatted_number as pivot_column,
            source_relation_type || '_' || `type` as input_column,
        from source_relation_parsed
        where `type` in ('mobile', 'landline')
    )

select *,
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
