{% macro region_to_city(column_name) %}
    /* values match dim_regions.name — keep the two in sync */
    case
        {{ column_name }}
        when 'TEAM Academy Charter School'
        then 'Newark'
        when 'KIPP Cooper Norcross Academy'
        then 'Camden'
        when 'KIPP Miami'
        then 'Miami'
        when 'KIPP Paterson'
        then 'Paterson'
        when 'KIPP TEAM and Family Schools Inc.'
        then 'TAF'
        else {{ column_name }}
    end
{% endmacro %}
