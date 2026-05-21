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
            coalesce(njs.lependdate, date '9999-12-31') as effective_date_end,
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
            coalesce(njs.liependdate2, date '9999-12-31') as effective_date_end,
        from {{ ref("stg_powerschool__s_nj_stu_x") }} as njs
        inner join
            student_lookup as sl
            on njs.studentsdcid = sl.students_dcid
            and njs._dbt_source_project = sl._dbt_source_project
        where njs.lepbegindate2 is not null
    ),

    nj_leg as (
        select *
        from nj_primary
        union all
        select *
        from nj_secondary
    ),

    pm_leg as (
        select
            enr.student_number,
            enr._dbt_source_project,
            min(enr.entrydate) as effective_date_start,
            date '9999-12-31' as effective_date_end,
        from {{ ref("base_powerschool__student_enrollments") }} as enr
        left join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on enr.students_dcid = scf.studentsdcid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="scf") }}
        where enr.region in ('Paterson', 'Miami') and scf.lep_status is true
        group by enr.student_number, enr._dbt_source_project
    ),

    unioned as (
        select *
        from nj_leg
        union all
        select *
        from pm_leg
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as ell_status_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    _dbt_source_project,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    true as is_ell,
    effective_date_end = date '9999-12-31' as is_current,
from unioned
