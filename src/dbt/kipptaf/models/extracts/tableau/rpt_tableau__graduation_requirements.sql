with
    parcc as (
        select
            local_student_identifier,
            test_scale_score as test_score,
            concat('parcc_', lower(test_code)) as test_type
        from parcc.summative_record_file_clean
        where test_code in ('ELA09', 'ELA10', 'ELA11', 'ALG01', 'GEO01', 'ALG02')
    ),
    sat as (
        select hs_student_id, [value] as test_score, concat('sat_', field) as test_type
        from
            (
                select
                    hs_student_id,
                    cast(
                        evidence_based_reading_writing as int
                    ) as evidence_based_reading_writing,
                    cast(math as int) as math,
                    cast(reading_test as int) as reading_test,
                    cast(math_test as int) as math_test
                from naviance.sat_scores
            ) as sub unpivot (
                [value] for field
                in (evidence_based_reading_writing, math, reading_test, math_test)
            ) as u
    ),
    act as (
        select
            st.score as test_score,
            left(st.score_type, len(st.score_type) - 2) as test_type,
            ktc.student_number
        from alumni.standardized_test_long as st
        inner join alumni.ktc_roster as ktc on (st.contact_c = ktc.sf_contact_id)
        where st.test_type = 'ACT' and st.score_type in ('act_reading_c', 'act_math_c')
    ),
    all_tests as (
        select local_student_identifier, test_type, test_score
        from parcc
        union all
        select hs_student_id, test_type, test_score
        from sat
        union all
        select student_number, test_type, test_score
        from act
    )
select
    co.student_number,
    co.lastfirst,
    co.grade_level,
    co.cohort,
    co.enroll_status,
    co.iep_status,
    co.c_504_status,
    co.is_retained_year,
    co.is_retained_ever,
    co.school_abbreviation,
    a.test_type,
    a.test_score
from powerschool.cohort_identifiers_static as co
left join all_tests as a on (co.student_number = a.local_student_identifier)
where
    co.academic_year = utilities.global_academic_year()
    and co.rn_year = 1
    and (
        co.cohort between (utilities.global_academic_year() - 1) and (
            utilities.global_academic_year() + 5
        )
    )
