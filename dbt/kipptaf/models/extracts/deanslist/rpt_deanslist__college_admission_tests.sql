select
    school_specific_id as student_number,
    test_type,
    act_composite,
    act_math,
    act_science,
    act_english,
    act_reading,
    act_writing,

    null as sat_total,
    null as sat_math,
    null as sat_reading,
    null as sat_writing,
    null as sat_mc,
    null as sat_essay,

    format_date('%b %Y', date) as test_date,
from {{ ref("int_kippadb__standardized_test") }}
where test_type = 'ACT' and act_composite is not null

union all

select
    school_specific_id as student_number,
    test_type,

    null as act_composite,
    null as act_math,
    null as act_science,
    null as act_english,
    null as act_reading,
    null as act_writing,

    sat_total_score as sat_total,

    coalesce(sat_math, sat_math_pre_2016) as sat_math,
    coalesce(sat_ebrw, sat_verbal, sat_critical_reading_pre_2016) as sat_reading,
    coalesce(sat_writing, sat_writing_pre_2016) as sat_writing,

    null as sat_mc,
    null as sat_essay,

    format_date('%b %Y', `date`) as test_date,
from {{ ref("int_kippadb__standardized_test") }}
where test_type = 'SAT' and sat_total_score is not null
