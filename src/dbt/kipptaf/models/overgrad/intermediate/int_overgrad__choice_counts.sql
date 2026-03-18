select
    student__external_student_id as contact_id,

    countif(top_choice_schools = '#1 Choice') as n_overgrad_1st_choice,
    countif(top_choice_schools = '#2 Choice') as n_overgrad_2nd_choice,
    countif(top_choice_schools = '#3 Choice') as n_overgrad_3rd_choice,

    countif(top_choice_schools = '#1 Choice') > 1 as has_duplicate_overgrad_1st_choice,
    countif(top_choice_schools = '#2 Choice') > 1 as has_duplicate_overgrad_2nd_choice,
    countif(top_choice_schools = '#3 Choice') > 1 as has_duplicate_overgrad_3rd_choice,
from {{ ref("int_overgrad__admissions") }}
where top_choice_schools is not null
group by student__external_student_id
