select
    academic_year_int as academic_year,
    concat('i-Ready ', lower(subject), ' typical growth') as domain,
    cast(if(student_grade = 'K', '0', student_grade) as numeric) as grade_level,
    round(
        avg(if(percent_progress_to_annual_typical_growth_percent >= 100, 1, 0)), 2
    ) as pct_met,
from {{ ref("base_iready__diagnostic_results") }}
where test_round = 'EOY' and rn_subj_round = 1
group by academic_year_int, subject, student_grade

union all

select
    academic_year_int as academic_year,
    concat('i-Ready ', lower(subject), ' stretch growth') as domain,
    cast(if(student_grade = 'K', '0', student_grade) as numeric) as grade_level,
    round(
        avg(if(percent_progress_to_annual_stretch_growth_percent >= 100, 1, 0)), 2
    ) as pct_met,
from {{ ref("base_iready__diagnostic_results") }}
where test_round = 'EOY' and rn_subj_round = 1
group by academic_year_int, subject, student_grade
