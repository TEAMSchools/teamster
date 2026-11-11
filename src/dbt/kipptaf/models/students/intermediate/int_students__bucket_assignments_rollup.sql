with
    deduped as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_students__bucket_assignments"),
                partition_by="academic_year, _dbt_source_project, student_number, subject",
                order_by="assignment_date desc",
            )
        }}
    )

select
    academic_year,
    _dbt_source_project,
    student_number,
    `subject`,
    bucket,
    bucket_store,
    assignment_date,
    n_active_assignments,
from deduped
