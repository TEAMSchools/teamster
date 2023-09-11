{{
  config(
    enabled=false
    )
}}

with
    category_grades as (
        select
            cat.studentid,
            cat.yearid,
            cat.schoolid,
            cat.course_number,
            cat.credittype,
            cat.storecode_type,
            cat.percent_grade,
            cat.citizenship_grade,
            'RT' || right(cat.storecode, 1) as reporting_term,
            if(
                current_date('{{ var("local_timezone") }}')
                between cat.termbin_start_date and cat.termbin_end_date,
                true,
                false
            ) as is_current,
        from {{ ref('int_powerschool__category_grades') }} as cat
    ),

    with_cur as (
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
        from category_grades

        union all

        select
            studentid,
            yearid,
            schoolid,
            credittype,
            course_number,

            'CUR' as reporting_term,

            is_current,
            storecode_type,
            percent_grade,
            citizenship_grade,
        from category_grades
        where is_current
    ),

    with_all as (
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
        from category_grades

        union all

        select
            studentid,
            yearid,
            schoolid,

            'ALL' as credittype,
            'ALL' as course_number,

            reporting_term,
            is_current,
            storecode_type,
            round(avg(percent_grade), 0) as percent_grade,

            null as citizenship_grade,
        from category_grades
        group by studentid, yearid, schoolid, reporting_term, is_current, storecode_type
    ),

    grades_pivot as (
        select
            studentid,
            yearid,
            schoolid
            credittype,
            course_number,
            reporting_term,
            is_current,
            value,
            concat(storecode_type, '_', rt) as pivot_field,
        from
            with_all pivot (
                max(percent_grade)
                for pivot_field in (
                    f_cur,
                    f_rt1,
                    f_rt2,
                    f_rt3,
                    f_rt4,
                    s_cur,
                    s_rt1,
                    s_rt2,
                    s_rt3,
                    s_rt4,
                    w_cur,
                    w_rt1,
                    w_rt2,
                    w_rt3,
                    w_rt4,
                    e_cur,
                    e_rt1,
                    e_rt2,
                    e_rt3,
                    e_rt4,
                    ctz_cur,
                    ctz_rt1,
                    ctz_rt2,
                    ctz_rt3,
                    ctz_rt4
                )
            )
    )

select
    studentid,
    yearid,
    schoolid,
    credittype,
    course_number,
    reporting_term,
    is_current,

    ctz_cur,
    ctz_rt1,
    ctz_rt2,
    ctz_rt3,
    ctz_rt4,

    {% for cat in ["f", "s", "w", "e"] %}
        {{ cat }}_cur,
        max({{ cat }}_rt1) over (
            partition by studentid, yearid, course_number order by reporting_term asc
        ) as {{ cat }}_rt1,
        max({{ cat }}_rt2) over (
            partition by studentid, yearid, course_number order by reporting_term asc
        ) as {{ cat }}_rt2,
        max({{ cat }}_rt3) over (
            partition by studentid, yearid, course_number order by reporting_term asc
        ) as {{ cat }}_rt3,
        max({{ cat }}_rt4) over (
            partition by studentid, yearid, course_number order by reporting_term asc
        ) as {{ cat }}_rt4,
        round(
            avg({{ cat }}_cur) over (
                partition by studentid, yearid, course_number
                order by reporting_term asc
            ),
            0
        ) as {{ cat }}_y1,
    {% endfor %}

    row_number() over (
        partition by studentid, yearid, reporting_term, credittype
        order by course_number asc
    ) as rn_credittype,
from grades_repivot
