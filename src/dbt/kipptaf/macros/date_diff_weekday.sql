{% macro date_diff_weekday(date_expression_a, date_expression_b) -%}
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
{%- endmacro %}
