with
    source as (
        -- trunk-ignore(sqlfluff/ST06)
        select
            state_student_identifier,
            last_or_surname,
            first_name,
            date_of_birth,
            scale_score,
            performance_level,
            test_name,
            testing_school,
            accountable_school,
            local_student_identifier,

            upper(_dagster_partition_test_type) as test_type,

            regexp_extract(
                _dagster_partition_administration_fiscal_year, r'([A-Za-z]+)\d+'
            ) as administration,

            cast(
                regexp_extract(
                    _dagster_partition_administration_fiscal_year, r'[A-Za-z]+(\d+)'
                ) as int
            ) as fiscal_year,
        from {{ source("pearson", "src_pearson__student_list_report") }}
    )

select *, fiscal_year - 1 as academic_year,
from source
