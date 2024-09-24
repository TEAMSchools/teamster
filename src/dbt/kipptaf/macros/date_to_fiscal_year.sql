{% macro date_to_fiscal_year(date_field, start_month, year_source) -%}
    if(
        extract(month from {{ date_field }}) >= {{ start_month }},
        {% if year_source == "start" -%}
            extract(year from {{ date_field }}), extract(year from {{ date_field }}) - 1
        {% elif year_source == "end" -%}
            extract(year from {{ date_field }}) + 1, extract(year from {{ date_field }})
        {%- endif %}
    )
{%- endmacro %}
