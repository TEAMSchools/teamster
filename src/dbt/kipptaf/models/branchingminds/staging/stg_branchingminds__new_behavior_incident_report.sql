with
    new_behavior_incident_report as (
        select
            source_detail_id,
            student_role,
            incident_type,
            incident_description,
            incident_location,
            action_taken,
            instructional_time_lost,
            antecedent,
            consequence,
            student_account,
            deescalation_strategy_student,
            deescalation_strategy_staff,
            restraint_used,
            seclusion_used,
            family_notified,
            police_notified,
            reporting_staff,
            data_source,
            district,
            `time` as incident_time,

            _dagster_partition_fiscal_year as source_fiscal_year,

            safe_cast(brm_detail_id as int64) as brm_detail_id,
            safe_cast(brm_incident_id as int64) as brm_incident_id,
            safe_cast(source_incident_id as int64) as source_incident_id,
            safe_cast(student_id as int64) as student_number,
            safe_cast(school_id as int64) as school_id,
            safe_cast(`date` as date) as incident_date,
            safe_cast(reported_date as date) as reported_date,
        from
            {{
                source(
                    "branchingminds",
                    "src_branchingminds__new_behavior_incident_report",
                )
            }}
    )

    {{
        dbt_utils.deduplicate(
            relation="new_behavior_incident_report",
            partition_by="brm_detail_id",
            order_by="source_fiscal_year desc",
        )
    }}
