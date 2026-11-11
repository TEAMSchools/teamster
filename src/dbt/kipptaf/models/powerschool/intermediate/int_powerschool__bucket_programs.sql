with
    programs as (
        select
            academic_year,
            student_number,
            exit_date,
            _dbt_source_project,
            enter_date as assignment_date,

            trim(split(specprog_name, '-')[offset(0)]) as bucket,

            case
                trim(split(specprog_name, '-')[safe_offset(1)])
                when 'ELA'
                then 'Reading'
                when 'Math'
                then 'Math'
            end as `subject`,
        from {{ ref("int_powerschool__spenrollments") }}
        where specprog_name like 'Bucket%'
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    assignments as (
        select
            academic_year,
            student_number,
            exit_date,
            _dbt_source_project,
            assignment_date,
            bucket,
            `subject`,

            exit_date is null
            or exit_date >= current_date('{{ var("local_timezone") }}') as is_active,

            countif(
                exit_date is null
                or exit_date >= current_date('{{ var("local_timezone") }}')
            ) over (
                partition by
                    academic_year, _dbt_source_project, student_number, `subject`
            ) as n_active_assignments,
        from programs
    ),

    deduped as (
        {{
            dbt_utils.deduplicate(
                relation="assignments",
                partition_by="academic_year, _dbt_source_project, student_number, subject, assignment_date",
                order_by="is_active desc, exit_date desc, bucket asc",
            )
        }}
    )

select
    academic_year,
    _dbt_source_project,
    student_number,
    `subject`,
    bucket,
    assignment_date,
    exit_date,
    n_active_assignments,
from deduped
