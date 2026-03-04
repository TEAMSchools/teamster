{% macro generate_cube_query(
    dimensions,
    metrics,
    source_relation,
    include_row_number=False,
    focus_group=False,
    focus_dims=[]
) %}

    select

        -- Dynamic dimensions
        {% for dim in dimensions %} {{ dim }},{% endfor %}

        -- Dynamic metrics
        {% for metric in metrics %} {{ metric }},{% endfor %}

        -- GROUPING() flags
        {% for dim in dimensions %}
            grouping({{ dim }}) as is_{{ dim }}_total,
        {% endfor %}

        -- grouping_level using POW + GROUPING()
        (
            {% for dim in dimensions %}
                grouping({{ dim }}) * pow(2, {{ loop.index0 }})
                {% if not loop.last %} + {% endif %}
            {% endfor %}
        ) as grouping_level,

        -- focus_level label for active focus dimension
        case
            {% for dim in focus_dims %}
                when
                    grouping({{ dim }}) = 0
                    and {% for other in focus_dims if other != dim %}
                        grouping({{ other }}) = 1{% if not loop.last %} and {% endif %}
                    {% endfor %}
                then '{{ dim }}'
            {% endfor %}
            when
                {% for dim in focus_dims %}
                    grouping({{ dim }}) = 1{% if not loop.last %} and {% endif %}
                {% endfor %}
            then 'all_null'
            else 'multi'
        end as focus_level,

        -- total_type: hierarchical label with grouping_level
        case
            when
                (
                    {% for dim in dimensions %}
                        grouping({{ dim }}) * pow(2, {{ loop.index0 }})
                        {% if not loop.last %} + {% endif %}
                    {% endfor %}
                )
                = 0
            then 'Level 0: Detail'

            when
                (
                    {% for dim in dimensions %}
                        grouping({{ dim }}) * pow(2, {{ loop.index0 }})
                        {% if not loop.last %} + {% endif %}
                    {% endfor %}
                )
                = {{ 2 ** (dimensions | length) - 1 }}
            then 'Level {{ 2 ** (dimensions | length) - 1 }}: Grand Total'

            else
                concat(
                    'Level ',
                    cast(
                        (
                            {% for dim in dimensions %}
                                grouping({{ dim }}) * pow(2, {{ loop.index0 }})
                                {% if not loop.last %} + {% endif %}
                            {% endfor %}
                        ) as string
                    ),
                    ': Subtotal – ',
                    array_to_string(
                        [
                            {% for dim in dimensions %}
                                if(grouping({{ dim }}) = 1, '{{ dim }}', null)
                                {% if not loop.last %}, {% endif %}
                            {% endfor %}
                        ],
                        ', '
                    )
                )
        end as total_type

    from {{ source_relation }}

    group by cube ({{ dimensions | join(", ") }})

    {% if focus_group and focus_dims %}
        having
            (
                (
                    {% for dim in focus_dims %}
                        cast(grouping({{ dim }}) = 0 as int64)
                        {% if not loop.last %} + {% endif %}
                    {% endfor %}
                )
                = 1
                or (
                    {% for dim in focus_dims %}
                        grouping({{ dim }}) = 1{% if not loop.last %} and {% endif %}
                    {% endfor %}
                )
            )
    {% endif %}

{% endmacro %}
