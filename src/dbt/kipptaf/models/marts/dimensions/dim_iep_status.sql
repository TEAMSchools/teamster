with
    nj_unioned as (
        select
            student_number,
            _dbt_source_project,
            special_education_code,
            special_education,
            nj_se_placement,
            effective_date,
            effective_end_date,

            -- edplan ships ~24% NULL spedlep; coalesce to 'No IEP' matches the
            -- base_powerschool__student_enrollments pattern and lets is_iep
            -- resolve to a non-null boolean for every row.
            coalesce(spedlep, 'No IEP') as spedlep,
        from {{ ref("int_edplan__njsmart_powerschool_union") }}
    ),

    nj_flagged as (
        select
            *,
            if(
                format(
                    '%T|%T|%T|%T',
                    spedlep,
                    special_education_code,
                    special_education,
                    nj_se_placement
                )
                = lag(
                    format(
                        '%T|%T|%T|%T',
                        spedlep,
                        special_education_code,
                        special_education,
                        nj_se_placement
                    )
                ) over (
                    partition by student_number, _dbt_source_project
                    order by effective_date
                ),
                0,
                1
            ) as is_island_start,
        from nj_unioned
    ),

    nj_islanded as (
        select
            *,
            sum(is_island_start) over (
                partition by student_number, _dbt_source_project order by effective_date
            ) as island_id,
        from nj_flagged
    ),

    nj_leg as (
        select
            student_number,
            _dbt_source_project,
            spedlep as iep_classification,
            special_education_code,
            special_education as special_education_name,
            cast(nj_se_placement as string) as special_education_placement,
            min(effective_date) as effective_date_start,
            coalesce(max(effective_end_date), date '9999-12-31') as effective_date_end,
        from nj_islanded
        group by
            student_number,
            _dbt_source_project,
            spedlep,
            special_education_code,
            special_education,
            nj_se_placement,
            island_id
    ),

    pm_leg as (
        -- trunk-ignore(sqlfluff/ST06): two-table join + aggregate + constants
        select
            enr.student_number,
            enr._dbt_source_project,
            coalesce(scf.spedlep, 'No IEP') as iep_classification,
            cast(null as string) as special_education_code,
            cast(null as string) as special_education_name,
            cast(null as string) as special_education_placement,
            min(enr.entrydate) as effective_date_start,
            date '9999-12-31' as effective_date_end,
        from {{ ref("base_powerschool__student_enrollments") }} as enr
        left join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on enr.students_dcid = scf.studentsdcid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="scf") }}
        where enr.region in ('Paterson', 'Miami')
        group by
            enr.student_number, enr._dbt_source_project, coalesce(scf.spedlep, 'No IEP')
    ),

    unioned as (
        select
            student_number,
            _dbt_source_project,
            iep_classification,
            special_education_code,
            special_education_name,
            special_education_placement,
            effective_date_start,
            effective_date_end,
        from nj_leg
        union all
        select
            student_number,
            _dbt_source_project,
            iep_classification,
            special_education_code,
            special_education_name,
            special_education_placement,
            effective_date_start,
            effective_date_end,
        from pm_leg
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as iep_status_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    _dbt_source_project,
    iep_classification,
    special_education_code,
    special_education_name,
    special_education_placement,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    iep_classification != 'No IEP' as is_iep,
    effective_date_end = date '9999-12-31' as is_current,
from unioned
