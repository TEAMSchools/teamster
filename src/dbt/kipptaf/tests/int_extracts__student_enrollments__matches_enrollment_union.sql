-- Rationale lives in this test's tests/properties.yml description.
-- Any returned row is a failure.
with
    extracts_keys as (
        -- grain projection, not dup-masking
        select distinct
            {{
                student_enrollment_key(
                    "student_number",
                    "_dbt_source_project",
                    "academic_year",
                    "entrydate",
                )
            }} as student_enrollment_key,
        from {{ ref("int_extracts__student_enrollments") }}
    ),

    union_keys as (
        -- grain projection, not dup-masking
        select distinct
            {{
                student_enrollment_key(
                    "student_number",
                    "_dbt_source_project",
                    "academic_year",
                    "entrydate",
                )
            }} as student_enrollment_key,
        from {{ ref("int_students__student_enrollment_union") }}
    )

select e.student_enrollment_key, 'missing from union' as gap,
from extracts_keys as e
left join union_keys as u on e.student_enrollment_key = u.student_enrollment_key
where u.student_enrollment_key is null

union all

select u.student_enrollment_key, 'missing from extracts' as gap,
from union_keys as u
left join extracts_keys as e on u.student_enrollment_key = e.student_enrollment_key
where e.student_enrollment_key is null
