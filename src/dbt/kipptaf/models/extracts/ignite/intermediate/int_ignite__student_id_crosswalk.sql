with
    /* grain projection, not dup-masking: one row per student across study
     years */
    population as (
        select distinct
            student_number, cast(student_number as string) as student_number_string,
        from {{ ref("int_ignite__student_years") }}
    ),

    hashed as (
        select
            p.student_number,

            farm_fingerprint(
                concat(s.salt, ':', p.student_number_string)
            ) as fingerprint,
        from population as p
        cross join {{ source("ignite", "ignite_id_salt") }} as s
    )

select student_number, mod(abs(fingerprint), 1000000000) as stu_id,
from hashed
