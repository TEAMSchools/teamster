with
    student_lookup as (
        select
            students_dcid, _dbt_source_project, min(student_number) as student_number,
        from {{ ref("base_powerschool__student_enrollments") }}
        group by students_dcid, _dbt_source_project
    ),

    nj_primary as (
        select
            sl.student_number,

            njs._dbt_source_project,
            njs.lepbegindate as effective_date_start,

            coalesce(njs.lependdate, cast('9999-12-31' as date)) as effective_date_end,
        from {{ ref("stg_powerschool__s_nj_stu_x") }} as njs
        inner join
            student_lookup as sl
            on njs.studentsdcid = sl.students_dcid
            and njs._dbt_source_project = sl._dbt_source_project
        where njs.lepbegindate is not null
    ),

    nj_secondary as (
        select
            sl.student_number,

            njs._dbt_source_project,
            njs.lepbegindate2 as effective_date_start,

            coalesce(
                njs.liependdate2, cast('9999-12-31' as date)
            ) as effective_date_end,
        from {{ ref("stg_powerschool__s_nj_stu_x") }} as njs
        inner join
            student_lookup as sl
            on njs.studentsdcid = sl.students_dcid
            and njs._dbt_source_project = sl._dbt_source_project
        where njs.lepbegindate2 is not null
    ),

    nj_leg as (
        select
            student_number,
            _dbt_source_project,
            effective_date_start,
            effective_date_end,
        from nj_primary
        union all
        select
            student_number,
            _dbt_source_project,
            effective_date_start,
            effective_date_end,
        from nj_secondary
    ),

    pm_leg as (
        select
            enr.student_number,
            enr._dbt_source_project,

            cast('9999-12-31' as date) as effective_date_end,

            min(enr.entrydate) as effective_date_start,
        from {{ ref("base_powerschool__student_enrollments") }} as enr
        left join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on enr.students_dcid = scf.studentsdcid
            and enr._dbt_source_project = scf._dbt_source_project
        -- Miami only: Paterson is already covered by stg_powerschool__s_nj_stu_x
        -- (NJ leg). Including Paterson here double-counts ELL spans.
        where enr.region = 'Miami' and scf.lep_status is true
        group by enr.student_number, enr._dbt_source_project
    ),

    unioned as (
        select
            student_number,
            _dbt_source_project,
            effective_date_start,
            effective_date_end,
        from nj_leg
        union all
        select
            student_number,
            _dbt_source_project,
            effective_date_start,
            effective_date_end,
        from pm_leg
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as student_ell_status_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    true as is_ell,
    effective_date_end = '9999-12-31' as is_current,
from unioned
