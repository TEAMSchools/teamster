with
    nj_unioned as (
        select
            student_number,
            _dbt_source_project,
            special_education_code,
            effective_date,

            special_education as special_education_name,

            cast(nj_se_placement as string) as special_education_placement,

            -- edplan ships ~24% NULL spedlep; coalesce so NULL and 'No IEP'
            -- rows group into one island instead of splitting on the lag().
            coalesce(spedlep, 'No IEP') as iep_classification,

            -- pre-coalesce the open-ended span sentinel so nj_leg can use a
            -- plain max() without re-handling NULL.
            coalesce(
                effective_end_date, cast('9999-12-31' as date)
            ) as effective_end_date,

            -- fingerprint for island detection in nj_flagged
            format(
                '%T|%T|%T|%T',
                coalesce(spedlep, 'No IEP'),
                special_education_code,
                special_education,
                nj_se_placement
            ) as island_fingerprint,
        from {{ ref("int_edplan__njsmart_powerschool_union") }}
        -- edplan emits ~147 rows with NULL student_number that would otherwise
        -- collapse into one phantom partition (NULL=NULL in window functions)
        -- and hash to the dbt_utils null-sentinel student_key, producing
        -- spurious PK collisions across unrelated upstream rows.
        where student_number is not null
    ),

    nj_flagged as (
        select
            *,

            if(
                island_fingerprint = lag(island_fingerprint) over (
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
            iep_classification,
            special_education_code,
            special_education_name,
            special_education_placement,

            min(effective_date) as effective_date_start,
            max(effective_end_date) as effective_date_end,
        from nj_islanded
        group by
            student_number,
            _dbt_source_project,
            iep_classification,
            special_education_code,
            special_education_name,
            special_education_placement,
            island_id
    ),

    pm_anchor as (
        select
            student_number, _dbt_source_project, min(entrydate) as effective_date_start,
        from {{ ref("base_powerschool__student_enrollments") }}
        where region in ('Paterson', 'Miami')
        group by student_number, _dbt_source_project
    ),

    pm_recent as (
        {{
            dbt_utils.deduplicate(
                relation=ref("base_powerschool__student_enrollments"),
                partition_by="student_number, _dbt_source_project",
                order_by="entrydate desc",
            )
        }}
    ),

    pm_leg as (
        select
            r.student_number,
            r._dbt_source_project,

            anchor.effective_date_start,

            cast('9999-12-31' as date) as effective_date_end,

            coalesce(scf.spedlep, 'No IEP') as iep_classification,
        from pm_recent as r
        inner join
            pm_anchor as anchor
            on r.student_number = anchor.student_number
            and r._dbt_source_project = anchor._dbt_source_project
        left join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on r.students_dcid = scf.studentsdcid
            and r._dbt_source_project = scf._dbt_source_project
        where r.region in ('Paterson', 'Miami')
    ),

    unioned as (
        select
            student_number,
            _dbt_source_project,
            iep_classification,
            effective_date_start,
            effective_date_end,
            special_education_code,
            special_education_name,
            special_education_placement,
        from nj_leg

        union all

        select
            student_number,
            _dbt_source_project,
            iep_classification,
            effective_date_start,
            effective_date_end,

            cast(null as string) as special_education_code,
            cast(null as string) as special_education_name,
            cast(null as string) as special_education_placement,
        from pm_leg
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as student_iep_status_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    iep_classification,
    special_education_code,
    special_education_name,
    special_education_placement,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    iep_classification != 'No IEP' as is_iep,
    effective_date_end = '9999-12-31' as is_current,
from unioned
