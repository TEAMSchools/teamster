with
    category_grades as (
        select
            studentid,
            yearid,
            schoolid,
            credittype,
            course_number,
            reporting_term,
            is_current,
            storecode_type,
            percent_grade,
            citizenship_grade,
            lower(storecode_type || '_' || reporting_term) as input_column,
        from {{ ref('int_powerschool__category_grades') }}
    ),

    with_cur as (
        select
            studentid,
            yearid,
            schoolid,
            credittype,
            course_number,
            is_current,
            storecode_type,
            percent_grade,
            input_column,

            'CUR' as reporting_term,
        from category_grades
        where is_current

        union all

        select
            studentid,
            yearid,
            schoolid,
            credittype,
            course_number,
            is_current,
            storecode_type,
            percent_grade,
            input_column,
            reporting_term,
        from category_grades
    ),

    with_all as (
        select
            studentid,
            yearid,
            schoolid,
            reporting_term,
            is_current,
            input_column,

            round(avg(percent_grade), 0) as percent_grade,

            'ALL' as credittype,
            'ALL' as course_number,
        from with_cur
        group by studentid, yearid, schoolid, reporting_term, is_current, input_column

        union all

        select
            studentid,
            yearid,
            schoolid,
            reporting_term,
            is_current,
            input_column,
            percent_grade,
            credittype,
            course_number,
        from with_cur
    ),

    grades_pivot as (
        select
            studentid,
            yearid,
            schoolid,
            credittype,
            course_number,
            reporting_term,
            is_current,
            {% for category in ["f", "s", "w", "e"] %}
                {% for term in ["cur", "rt1", "rt2", "rt3", "rt4"] %}
                    {{ category }}_{{ term }},
                {% endfor %}
            {% endfor %}
        from
            with_all pivot (
                max(percent_grade) for input_column in (
                    {%- for category in ["f", "s", "w", "e"] -%}
                        {%- for term in ["cur", "rt1", "rt2", "rt3", "rt4"] -%}
                            '{{ category }}_{{ term }}'
                            {%- if not loop.last %},{% endif -%}
                        {% endfor %}
                        {%- if not loop.last %},{% endif -%}
                    {% endfor %}
                )
            )
    ),

    ctz_pivot as (
        select
            studentid,
            yearid,
            course_number,
            reporting_term,
            {%- for term in ["cur", "rt1", "rt2", "rt3", "rt4"] -%}
                ctz_{{ term }},
            {% endfor %}
        from
            category_grades pivot (
                max(citizenship_grade) for input_column in (
                    {% for term in ["cur", "rt1", "rt2", "rt3", "rt4"] -%}
                        'q_{{ term }}' as `ctz_{{ term }}`
                        {%- if not loop.last %},{% endif %}
                    {% endfor %}
                )
            )
        where storecode_type = 'Q'
    )

select
    gp.studentid,
    gp.yearid,
    gp.schoolid,
    gp.credittype,
    gp.course_number,
    gp.reporting_term,
    gp.is_current,

    {% for cat in ["f", "s", "w", "e"] %}
        {% for term in ["rt1", "rt2", "rt3", "rt4"] %}
            max(gp.{{ cat }}_{{ term }}) over (
                partition by gp.studentid, gp.yearid, gp.course_number
                order by gp.reporting_term asc
            ) as {{ cat }}_{{ term }},
        {% endfor %}
        gp.{{ cat }}_cur,

        round(
            avg(gp.{{ cat }}_cur) over (
                partition by gp.studentid, gp.yearid, gp.course_number
                order by gp.reporting_term asc
            ),
            0
        ) as {{ cat }}_y1,
    {% endfor %}

    row_number() over (
        partition by gp.studentid, gp.yearid, gp.reporting_term, gp.credittype
        order by gp.course_number asc
    ) as rn_credittype,

    {% for term in ["rt1", "rt2", "rt3", "rt4"] %}
        max(ctz.ctz_{{ term }}) over (
            partition by gp.studentid, gp.yearid, gp.course_number
            order by gp.reporting_term asc
        ) as ctz_{{ term }},
    {% endfor %}
    ctz.ctz_cur,
from grades_pivot as gp
left join
    ctz_pivot as ctz
    on gp.studentid = ctz.studentid
    and gp.yearid = ctz.yearid
    and gp.course_number = ctz.course_number
    and gp.reporting_term = ctz.reporting_term
