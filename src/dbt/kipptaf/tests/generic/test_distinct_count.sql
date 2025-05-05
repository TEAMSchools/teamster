{% test distinct_count(model, group_by, distinct_field) %}

    with
        base as (
            select
                {{ group_by }} as {{ group_by }},
                count(distinct {{ distinct_field }}) as {{ distinct_field }},
            from {{ model }}
            group by {{ group_by }}
        )

    select *,
    from base
    where {{ distinct_field }} > 1

{% endtest %}
