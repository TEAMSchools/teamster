{% macro parse_html(column_name) %}
    {#- &amp; decodes last, so an escaped &amp;lt; is not decoded twice -#}
    {%- set entities = [
        ("&#39;", '"\'"'),
        ("&quot;", "'\"'"),
        ("&nbsp;", "' '"),
        ("&ldquo;", "'\"'"),
        ("&rdquo;", "'\"'"),
        ("&lsquo;", '"\'"'),
        ("&rsquo;", '"\'"'),
        ("&mdash;", "'—'"),
        ("&ndash;", "'–'"),
        ("&hellip;", "'…'"),
        ("&bull;", "'•'"),
        ("&lt;", "'<'"),
        ("&gt;", "'>'"),
        ("&amp;", "'&'"),
    ] -%}
    {%- set ns = namespace(expr=column_name) -%}
    {%- for entity, literal in entities -%}
        {%- set args = ns.expr ~ ", '" ~ entity ~ "', " ~ literal -%}
        {%- set ns.expr = "replace(" ~ args ~ ")" -%}
    {%- endfor -%}
    trim(
        regexp_replace(
            regexp_replace(
                regexp_replace({{ ns.expr }}, r'<[^>]+>', ''), r'\r|\n', ' '
            ),
            r'\s+',
            ' '
        )
    )
{% endmacro %}
