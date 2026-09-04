{# KTAF-assigned Branching Minds district codes (not a state or vendor id).
   `region` is any expression yielding the region name: `dr.name` on a mart,
   or extract_region("alias") on a union model. #}
{% macro branchingminds_district_id(region) -%}
    case
        {{ region }}
        when 'Newark'
        then '7325'
        when 'Camden'
        then '1799'
        when 'Paterson'
        then '7899'
    end
{%- endmacro %}

{# Official first day of school where it differs from the school calendar.
   Keyed by academic year so a new year yields NULL and the caller's
   coalesce() falls back to the calendar's first in-session day. SY26-27:
   the calendar marks 8/19-8/23 in-session for Newark/Paterson too, but their
   official first day was 8/24 (Camden opened 8/19). #}
{% macro branchingminds_first_day_override(region, academic_year) -%}
    case
        when {{ academic_year }} = 2026
        then
            case
                {{ region }} when 'Camden' then date '2026-08-19' else date '2026-08-24'
            end
    end
{%- endmacro %}
