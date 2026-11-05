with
    -- grain projection, not dup-masking: each archive studentid maps to 1
    -- student_number
    miami_archive_student_numbers as (
        select distinct studentid, student_number, _dbt_source_project,
        from {{ ref("int_powerschool__ada") }}
        where _dbt_source_project = 'kippmiami'
    ),

    powerschool_programs as (
        select
            sp.academic_year,
            sp.exit_date,
            sp._dbt_source_project,
            sp.enter_date as assignment_date,

            'powerschool' as bucket_store,

            coalesce(co.student_number, an.student_number) as student_number,

            trim(split(sp.specprog_name, '-')[offset(0)]) as bucket,

            case
                trim(split(sp.specprog_name, '-')[safe_offset(1)])
                when 'ELA'
                then 'Reading'
                when 'Math'
                then 'Math'
            end as `subject`,
        from {{ ref("int_powerschool__spenrollments") }} as sp
        left join
            {{ ref("int_extracts__student_enrollments") }} as co
            on sp.studentid = co.studentid
            and sp.academic_year = co.academic_year
            and sp._dbt_source_project = co._dbt_source_project
            and co.rn_year = 1
        left join
            miami_archive_student_numbers as an
            on sp.studentid = an.studentid
            and sp._dbt_source_project = an._dbt_source_project
        where sp.specprog_name like 'Bucket%'
    ),

    focus_memberships as (
        select
            _dbt_source_project,
            syear as academic_year,
            student_id as student_number,
            end_date as exit_date,

            'focus' as bucket_store,

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
        where title like 'Bucket%'
    ),

    assignment_union as (
        select
            academic_year,
            _dbt_source_project,
            student_number,
            `subject`,
            bucket,
            bucket_store,
            assignment_date,
            exit_date,
        from powerschool_programs
        where student_number is not null

        union all

        select
            academic_year,
            _dbt_source_project,
            student_number,
            `subject`,
            bucket,
            bucket_store,
            assignment_date,
            exit_date,
        from focus_memberships
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    assignments as (
        select
            academic_year,
            _dbt_source_project,
            student_number,
            `subject`,
            bucket,
            bucket_store,
            assignment_date,
            exit_date,

            exit_date is null
            or exit_date >= current_date('{{ var("local_timezone") }}') as is_active,

            countif(
                exit_date is null
                or exit_date >= current_date('{{ var("local_timezone") }}')
            ) over (
                partition by
                    academic_year, _dbt_source_project, student_number, `subject`
            ) as n_active_assignments,
        from assignment_union
    ),

    deduped as (
        {{
            dbt_utils.deduplicate(
                relation="assignments",
                partition_by="academic_year, _dbt_source_project, student_number, subject",
                order_by="assignment_date desc, is_active desc, exit_date desc, bucket desc",
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
