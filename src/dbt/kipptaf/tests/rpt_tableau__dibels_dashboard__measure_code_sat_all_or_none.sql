with
    code_group as (
        select
            academic_year,
            model_type,
            student_number,
            expected_test,
            expected_round_number,
            expected_measure_name_code,

            count(*) as n_expected_standards,

            countif(measure_standard_score is not null) as n_standards_sat,

        from {{ ref("rpt_tableau__dibels_dashboard") }}
        where assessment_type = 'PM'
        group by
            academic_year,
            model_type,
            student_number,
            expected_test,
            expected_round_number,
            expected_measure_name_code
    )

select
    academic_year,
    model_type,
    student_number,
    expected_test,
    expected_round_number,
    expected_measure_name_code,
    n_expected_standards,
    n_standards_sat,

from code_group
where
    n_expected_standards > 1 and n_standards_sat between 1 and n_expected_standards - 1
