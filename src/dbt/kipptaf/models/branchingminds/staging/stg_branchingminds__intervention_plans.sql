with
    intervention_plans as (
        select
            intervention_name,
            intervention_subject_area,
            support_used_as,
            support_type,
            support_evidence_level,
            technology_required,
            support_cost,
            intervention_setting,
            staff_delivering_intervention,
            staff_email,
            district,

            _dagster_partition_fiscal_year as source_fiscal_year,

            safe_cast(intervention_plan_id as int64) as intervention_plan_id,
            safe_cast(student_id as int64) as student_number,
            safe_cast(school_id as int64) as school_id,
            safe_cast(school_year as int64) as school_year,
            safe_cast(intervention_frequency as int64) as intervention_frequency,
            safe_cast(duration_per_occurrence as int64) as duration_per_occurrence,
            safe_cast(total_minutes_planned as numeric) as total_minutes_planned,
            safe_cast(total_minutes_delivered as numeric) as total_minutes_delivered,
            safe_cast(intervention_start_date as date) as intervention_start_date,
            safe_cast(intervention_end_date as date) as intervention_end_date,

            json_value_array(applicable_tiers) as applicable_tiers,
            json_value_array(support_tags) as support_tags,
        from {{ source("branchingminds", "src_branchingminds__intervention_plans") }}
    )

    {{
        dbt_utils.deduplicate(
            relation="intervention_plans",
            partition_by="intervention_plan_id",
            order_by="source_fiscal_year desc",
        )
    }}
