with
    memberships as (
        select
            _dbt_source_project,
            syear as academic_year,
            student_id as student_number,
            end_date as exit_date,

            cast(created_at as date) as assignment_date,

            trim(split(title, '-')[offset(0)]) as bucket,

            case
                trim(split(title, '-')[safe_offset(1)])
                when 'ELA'
                then 'Reading'
                when 'Math'
                then 'Math'
            end as `subject`,
        from {{ ref("int_focus__student_group_memberships") }}
        -- Miami's Focus cutover year: the frozen PowerSchool archive owns
        -- Miami's buckets before it
        where title like 'Bucket%' and syear >= 2026
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    assignments as (
        select
            _dbt_source_project,
            academic_year,
            student_number,
            exit_date,
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
        from memberships
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
