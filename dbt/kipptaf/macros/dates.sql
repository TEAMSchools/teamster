{% macro date_to_fiscal_year(date_field, start_month, year_source) %}
    if(
        extract(month from {{ date_field }}) >= {{ start_month }},
        {% if year_source == "start" -%}
            extract(year from {{ date_field }}), extract(year from {{ date_field }}) - 1
        {% elif year_source == "end" -%}
            extract(year from {{ date_field }}) + 1, extract(year from {{ date_field }})
        {%- endif %}
    )
{% endmacro %}

{% macro current_school_year(local_timezone) %}
    {{
        date_to_fiscal_year(
            date_field="current_date('" + local_timezone + "')",
            start_month=7,
            year_source="start",
        )
    }}
{% endmacro %}

{% macro date_diff_weekday(date_expression_a, date_expression_b) %}
    if(
        date_diff(
            safe_cast({{ date_expression_b }} as date),
            safe_cast({{ date_expression_a }} as date),
            week
        )
        > 0,
        date_diff(
            safe_cast({{ date_expression_b }} as date),
            safe_cast({{ date_expression_a }} as date),
            day
        ) - (
            date_diff(
                safe_cast({{ date_expression_b }} as date),
                safe_cast({{ date_expression_a }} as date),
                week
            )
            * 2
        ),
        date_diff(
            safe_cast({{ date_expression_b }} as date),
            safe_cast({{ date_expression_a }} as date),
            day
        )
    )
{% endmacro %}
