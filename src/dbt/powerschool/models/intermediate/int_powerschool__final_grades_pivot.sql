with
    grades_union as (
        select
            studentid,
            yearid,
            course_number,
            sectionid,
            storecode,
            y1_percent_grade_adjusted,
            y1_letter_grade,
            need_90,
            need_80,
            need_70,
            need_60,
            term_percent_grade,
            term_letter_grade,
            term_percent_grade_adjusted,
            term_letter_grade_adjusted,
            storecode as reporting_term,
        from {{ ref('base_powerschool__final_grades') }}

        union all

        select
            studentid,
            yearid,
            course_number,
            sectionid,
            storecode,
            y1_percent_grade_adjusted,
            y1_letter_grade,
            need_90,
            need_80,
            need_70,
            need_60,
            term_percent_grade,
            term_letter_grade,
            term_percent_grade_adjusted,
            term_letter_grade_adjusted,
            'CUR' as reporting_term,
        from {{ ref('base_powerschool__final_grades') }}
        where
            current_date('{{ var("local_timezone") }}')
            between termbin_start_date and termbin_end_date
    ),

    grades_pivot as (
        select *
        from
            grades_union pivot (
                max(term_letter_grade) as term_letter_grade,
                max(term_percent_grade) as term_percent_grade,
                max(term_letter_grade_adjusted) as term_letter_grade_adjusted,
                max(
                    term_percent_grade_adjusted
                ) as term_percent_grade_adjusted for reporting_term
                in ('Q1' as rt1, 'Q2' as rt2, 'Q3' as rt3, 'Q4' as rt4, 'CUR' as cur)
            )
    )

select
    studentid,
    yearid,
    course_number,
    sectionid,
    storecode,
    y1_letter_grade,
    y1_percent_grade_adjusted,
    need_90,
    need_80,
    need_70,
    need_60,

    term_percent_grade_cur,
    term_letter_grade_cur,
    term_percent_grade_adjusted_cur,
    term_letter_grade_adjusted_cur,

    {% for term in ["rt1", "rt2", "rt3", "rt4"] %}
        max(term_percent_grade_{{ term }}) over (
            partition by studentid, yearid, course_number order by storecode asc
        ) as term_percent_grade_{{ term }},
        max(term_letter_grade_{{ term }}) over (
            partition by studentid, yearid, course_number order by storecode asc
        ) as term_letter_grade_{{ term }},
        max(term_percent_grade_adjusted_{{ term }}) over (
            partition by studentid, yearid, course_number order by storecode asc
        ) as term_percent_grade_adjusted_{{ term }},
        max(term_letter_grade_adjusted_{{ term }}) over (
            partition by studentid, yearid, course_number order by storecode asc
        ) as term_letter_grade_adjusted_{{ term }},
    {% endfor %}
from grades_pivot
