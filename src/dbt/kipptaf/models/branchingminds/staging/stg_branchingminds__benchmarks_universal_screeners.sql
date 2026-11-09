with
    benchmarks_universal_screeners as (
        select
            network,
            subject_area,
            assessment_provider,
            assessment,
            level,
            `description`,
            staff,
            district,
            school as school_name,
            `window` as assessment_window,

            _dagster_partition_fiscal_year as source_fiscal_year,

            safe_cast(score_id as int64) as score_id,
            safe_cast(student_id as int64) as student_number,
            safe_cast(school_year as int64) as school_year,
            safe_cast(score as numeric) as score,
            safe_cast(percentile as int64) as percentile,
            safe_cast(growth_percentile as int64) as growth_percentile,
            safe_cast(assessment_date as date) as assessment_date,

            json_value_array(student_tags) as student_tags,
        from
            {{
                source(
                    "branchingminds",
                    "src_branchingminds__benchmarks_universal_screeners",
                )
            }}
    )

    {{
        dbt_utils.deduplicate(
            relation="benchmarks_universal_screeners",
            partition_by="score_id",
            order_by="source_fiscal_year desc",
        )
    }}
