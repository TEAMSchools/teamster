select
    _dbt_source_relation,
    studentid,
    academic_year,
    schoolid,
    storecode,

    sum(potential_credit_hours) as enrolled_credit_hours,

    sum(if(y1_letter_grade_adjusted in ('F', 'F*'), 1, 0)) as n_failing,
    sum(
        if(
            y1_letter_grade_adjusted in ('F', 'F*')
            and credittype in ('ENG', 'MATH', 'SCI', 'SOC'),
            1,
            0
        )
    ) as n_failing_core,
    sum(
        {# TODO: exclude credits if current year Y1 is stored #}
        if(y1_letter_grade_adjusted not in ('F', 'F*'), potential_credit_hours, null)
    ) as projected_credits_y1_term,
from {{ ref("base_powerschool__final_grades") }}
group by _dbt_source_relation, studentid, academic_year, schoolid, storecode
