{% test branchingminds_school_year_matches_partition(model, column_name) %}

    with
        partitions as (
            select source_fiscal_year, max({{ column_name }}) as max_school_year,
            from {{ model }}
            group by source_fiscal_year
        )

    select source_fiscal_year, max_school_year,
    from partitions
    where max_school_year != source_fiscal_year

{% endtest %}
