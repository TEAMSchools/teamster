with
    intervention_notes as (
        select
            notes,
            district,

            _dagster_partition_fiscal_year as source_fiscal_year,

            safe_cast(intervention_plan_id as int64) as intervention_plan_id,
            safe_cast(notes_date as date) as notes_date,
        from {{ source("branchingminds", "src_branchingminds__intervention_notes") }}
    )

    {{
        dbt_utils.deduplicate(
            relation="intervention_notes",
            partition_by="intervention_plan_id, notes_date, notes",
            order_by="source_fiscal_year desc",
        )
    }}
