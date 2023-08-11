select
    ktc.school_specific_id as student_number,

    st.test_type,
    st.act_composite,
    st.act_math,
    st.act_science,
    st.act_english,
    st.act_reading,
    st.act_writing,
    null as sat_total,
    null as sat_math,
    null as sat_reading,
    null as sat_writing,
    null as sat_mc,
    null as sat_essay,
    format_date('%b %Y', st.date) as test_date,
from {{ ref("stg_kippadb__contact") }} as ktc
inner join {{ ref("stg_kippadb__standardized_test") }} as st on ktc.id = st.contact
where st.test_type = 'ACT' and st.act_composite is not null

union all

select
    ktc.school_specific_id as student_number,

    st.test_type,
    null as act_composite,
    null as act_math,
    null as act_science,
    null as act_english,
    null as act_reading,
    null as act_writing,
    st.sat_total_score as sat_total,
    coalesce(st.sat_math, st.sat_math_pre_2016) as sat_math,
    coalesce(
        st.sat_ebrw, st.sat_verbal, st.sat_critical_reading_pre_2016
    ) as sat_reading,
    coalesce(st.sat_writing, st.sat_writing_pre_2016) as sat_writing,
    null as sat_mc,
    null as sat_essay,
    format_date('%b %Y', st.date) as test_date,
from {{ ref("stg_kippadb__contact") }} as ktc
inner join {{ ref("stg_kippadb__standardized_test") }} as st on ktc.id = st.contact
where st.test_type = 'SAT' and st.sat_total_score is not null
