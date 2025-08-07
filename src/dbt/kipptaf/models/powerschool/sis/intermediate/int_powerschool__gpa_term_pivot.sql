with
    gpa as (
        select _dbt_source_relation, studentid, yearid, term_name, gpa_term, gpa_y1,
        from {{ ref("int_powerschool__gpa_term") }}

        union all

        select
            _dbt_source_relation,
            studentid,
            yearid,
            'CUR' as term_name,
            gpa_term,
            gpa_y1,
        from {{ ref("int_powerschool__gpa_term") }}
        where is_current
    )

select
    _dbt_source_relation,
    studentid,
    yearid,

    /* pivot fields */
    gpa_term_cur,
    gpa_term_q1,
    gpa_term_q2,
    gpa_term_q3,
    gpa_term_q4,
    gpa_y1_cur,
    gpa_y1_q1,
    gpa_y1_q2,
    gpa_y1_q3,
    gpa_y1_q4,
from
    gpa pivot (
        max(gpa_term) as gpa_term,
        max(gpa_y1) as gpa_y1
        for term_name in ('Q1', 'Q2', 'Q3', 'Q4', 'CUR')
    )
