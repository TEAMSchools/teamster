{% macro clean_phone(column) %}
    {#-
      Normalize a raw phone to E.164:
        - US (bare 10, +1, or 11-digit leading 1, NANP-valid) -> +1XXXXXXXXXX
        - explicit international (+<cc!=1> or 011<cc>)         -> +<cc><national>
        - explicit x/ext extension                            -> append x<ext>
      Anything not confidently parseable passes through the de-garbled original
      (control chars stripped). Never returns NULL for a non-null input.
    -#}
    {%- set degarbled -%}
        trim(regexp_replace({{ column }}, r'[^\x20-\x7E]', ''))
    {%- endset -%}
    {%- set ext -%}
        regexp_extract(
            {{ degarbled }}, r'(?i)(?:ext\.?|extension|x)\s*(\d{1,6})\s*$'
        )
    {%- endset -%}
    {%- set main -%}
        regexp_replace(
            {{ degarbled }}, r'(?i)\s*(?:ext\.?|extension|x)\s*\d{1,6}\s*$', ''
        )
    {%- endset -%}
    {%- set digits -%} regexp_replace({{ main }}, r'\D', '') {%- endset -%}
    coalesce(
        case
            when
                regexp_contains({{ main }}, r'^\s*\+')
                and not regexp_contains({{ main }}, r'^\s*\+\s*1')
                and length({{ digits }}) between 8 and 15
            then '+' || {{ digits }}
            when
                starts_with({{ digits }}, '011')
                and length({{ digits }}) between 11 and 18
            then '+' || substr({{ digits }}, 4)
            when
                length({{ digits }}) = 10
                and regexp_contains({{ digits }}, r'^[2-9]\d{2}[2-9]\d{6}$')
            then '+1' || {{ digits }}
            when
                length({{ digits }}) = 11
                and starts_with({{ digits }}, '1')
                and regexp_contains(substr({{ digits }}, 2), r'^[2-9]\d{2}[2-9]\d{6}$')
            then '+1' || substr({{ digits }}, 2)
        end
        || if({{ ext }} is not null, 'x' || {{ ext }}, ''),
        {{ degarbled }}
    )
{% endmacro %}
