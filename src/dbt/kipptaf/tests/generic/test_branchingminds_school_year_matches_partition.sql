{% test branchingminds_school_year_matches_partition(model, column_name) %}

    {#- older partitions keep only rows a newer partition did not supersede -#}
    with
        latest as (
            select max(source_fiscal_year) as source_fiscal_year, from {{ model }}
        ),

        partitions as (
            select m.source_fiscal_year, max(m.{{ column_name }}) as max_school_year,
            from {{ model }} as m
            inner join latest as l on m.source_fiscal_year = l.source_fiscal_year
            group by m.source_fiscal_year
        )

    select source_fiscal_year, max_school_year,
    from partitions
    where max_school_year != source_fiscal_year

{% endtest %}
