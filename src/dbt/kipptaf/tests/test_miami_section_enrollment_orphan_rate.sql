with
    miami_current_year as (
        select d.student_enrollment_key,
        from {{ ref("dim_student_section_enrollments") }} as d
        inner join
            {{ ref("int_students__course_enrollments") }} as cc
            on d.student_section_enrollment_key
            = {{
                dbt_utils.generate_surrogate_key(
                    ["cc.cc_dcid", "cc._dbt_source_project"]
                )
            }}
        where
            cc._dbt_source_project = 'kippmiami'
            and d.academic_year = {{ var("current_academic_year") }}
    )

select
    count(*) as total_rows,
    countif(student_enrollment_key is null) as orphaned_rows,
    safe_divide(countif(student_enrollment_key is null), count(*)) as orphan_rate,
from miami_current_year
having orphan_rate > 0.15
