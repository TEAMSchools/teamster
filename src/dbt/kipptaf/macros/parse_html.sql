{% macro parse_html(column_name) %}
    coalesce(
        trim(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        replace(
                            replace(
                                replace(
                                    replace(
                                        replace({{ column_name }}, '&#39;', "'"),
                                        '&quot;',
                                        '"'
                                    ),
                                    '&lt;',
                                    '<'
                                ),
                                '&gt;',
                                '>'
                            ),
                            '&amp;',
                            '&'
                        ),
                        r'<[^>]+>',
                        ''
                    ),
                    r'\r|\n',
                    ' '
                ),
                r'\s+',
                ' '
            )
        ),
        'Blank'
    )
{% endmacro %}
