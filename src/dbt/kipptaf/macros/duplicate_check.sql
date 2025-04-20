{% test duplicate_check(model, group_by, distinct_field, operator=">", threshold=1) %}
    with
        base as (
            select
                {{ group_by }} as group_val,
                count(distinct {{ distinct_field }}) as distinct_count,
            from {{ model }}
            group by {{ group_by }}
        )

    select *
    from base
    where distinct_count {{ operator }} {{ threshold }}
{% endtest %}
