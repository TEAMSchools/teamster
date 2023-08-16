with
    parcc as (
        select
            localstudentidentifier as student_number,
            testscalescore as test_score,
            concat('parcc_', lower(testcode)) as test_type,
        from {{ ref("stg_pearson__parcc") }}
        where testcode in ('ELA09', 'ELA10', 'ELA11', 'ALG01', 'GEO01', 'ALG02')
    ),

    {# TODO: add SAT from salesforce #}
    act as (
        select
            st.score as test_score,
            st.score_type as test_type,

            ktc.school_specific_id as student_number,
        from {{ ref("int_kippadb__standardized_test_unpivot") }} as st
        inner join {{ ref("stg_kippadb__contact") }} as ktc on st.contact = ktc.id
        where st.test_type = 'ACT' and st.score_type in ('act_reading', 'act_math')
    ),

    all_tests as (
        select student_number, test_type, test_score,
        from parcc

        union all

        select student_number, test_type, test_score,
        from act
    )

select
    co.student_number,
    co.lastfirst,
    co.school_abbreviation,
    co.grade_level,
    co.cohort,
    co.enroll_status,
    co.spedlep as iep_status,
    co.is_504 as c_504_status,
    co.is_retained_year,
    co.is_retained_ever,

    a.test_type,
    a.test_score,
from {{ ref("base_powerschool__student_enrollments") }} as co
left join all_tests as a on co.student_number = a.student_number
where
    co.rn_year = 1
    and co.academic_year = {{ var("current_academic_year") }}
    and co.cohort between ({{ var("current_academic_year") }} - 1) and (
        {{ var("current_academic_year") }} + 5
    )
