with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("adp_workforce_now", "person_history"),
                partition_by="worker_id",
                order_by="_fivetran_synced desc",
            )
        }}
    ),

    transformations as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            * except (preferred_name_given_name, preferred_name_middle_name),

            case
                race_long_name
                when 'Black or African American'
                then 'Black/African American'
                when 'Hispanic or Latino'
                then 'Latinx/Hispanic/Chicana(o)'
                when 'Two or more races (Not Hispanic or Latino)'
                then 'Bi/Multiracial'
                else race_long_name
            end as race_ethnicity_reporting,

            coalesce(
                preferred_name_given_name, legal_name_given_name
            ) as preferred_name_given_name,
            coalesce(
                preferred_name_middle_name, legal_name_middle_name
            ) as preferred_name_middle_name,
            coalesce(
                preferred_name_family_name_1, legal_name_family_name_1
            ) as preferred_name_family_name,
        from deduplicate
    )

select
    *,

    preferred_name_family_name
    || ', '
    || preferred_name_given_name as preferred_name_lastfirst,
from transformations
