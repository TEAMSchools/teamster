with
    population as (
        select distinct student_number,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            academic_year in ({{ var("ignite_academic_years") | join(", ") }})
            and grade_level in ({{ var("ignite_grade_levels") | join(", ") }})
            and region in ({{ "'" ~ (var("ignite_regions") | join("', '")) ~ "'" }})
            and student_number is not null
    ),

    keyed as (
        select student_number, cast(student_number as string) as student_number_string,
        from population
    ),

    hashed as (
        select
            student_number,

            farm_fingerprint(
                concat('{{ var("ignite_id_salt") }}:', student_number_string)
            ) as fingerprint,
        from keyed
    )

select student_number, mod(abs(fingerprint), 1000000000) as stu_id,
from hashed
