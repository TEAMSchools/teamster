with
    powerschool_programs as (
        select
            sp.academic_year,
            sp.exit_date,
            sp.enter_date as assignment_date,

            co.student_number,

            'powerschool' as bucket_store,

            trim(split(sp.specprog_name, '-')[offset(0)]) as bucket,
            trim(split(sp.specprog_name, '-')[offset(1)]) as discipline,

            initcap(regexp_extract(sp._dbt_source_relation, r'kipp(\w+)_')) as region,
        from {{ ref("int_powerschool__spenrollments") }} as sp
        inner join
            {{ ref("int_extracts__student_enrollments") }} as co
            on sp.studentid = co.studentid
            and sp.academic_year = co.academic_year
            and sp._dbt_source_project = co._dbt_source_project
        where sp.specprog_name like 'Bucket%' and co.rn_year = 1
    ),

    focus_memberships as (
        select
            sg.end_date as exit_date,

            jg.syear as academic_year,
            jg.student_id as student_number,

            'Miami' as region,
            'focus' as bucket_store,

            cast(jg.created_at as date) as assignment_date,

            trim(split(sg.title, '-')[offset(0)]) as bucket,
            trim(split(sg.title, '-')[offset(1)]) as discipline,
        from {{ ref("stg_focus__students_join_groups") }} as jg
        inner join
            {{ ref("stg_focus__student_groups") }} as sg
            on jg.group_id = sg.id
            and jg._dbt_source_project = sg._dbt_source_project
        where sg.title like 'Bucket%'
    ),

    assignment_union as (
        select
            academic_year,
            region,
            student_number,
            discipline,
            bucket,
            bucket_store,
            assignment_date,
            exit_date,
        from powerschool_programs

        union all

        select
            academic_year,
            region,
            student_number,
            discipline,
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
            region,
            student_number,
            bucket,
            bucket_store,
            assignment_date,

            if(discipline = 'ELA', 'Reading', 'Math') as `subject`,

            countif(exit_date is null) over (
                partition by academic_year, region, student_number, discipline
            ) as n_active_assignments,
        from assignment_union
    ),

    deduped as (
        {{
            dbt_utils.deduplicate(
                relation="assignments",
                partition_by="academic_year, region, student_number, subject",
                order_by="assignment_date desc",
            )
        }}
    )

select
    academic_year,
    region,
    student_number,
    `subject`,
    bucket,
    bucket_store,
    assignment_date,
    n_active_assignments,
from deduped
