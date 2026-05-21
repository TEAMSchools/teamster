with
    nj_unioned as (
        select
            _dbt_source_project,
            eligibility_start_date,
            eligibility_end_date,

            person_identifier as student_number,

            -- titan staging `eligibility_name` is single-letter (F/R/P); 2 NULLs
            -- in the source coalesce to 'Unknown' so the is_meal_eligible
            -- derivation never returns NULL.
            coalesce(eligibility_name, 'Unknown') as eligibility_name,
        from {{ ref("stg_titan__person_data") }}
        where eligibility_start_date is not null
    ),

    nj_flagged as (
        select
            *,
            if(
                eligibility_name = lag(eligibility_name) over (
                    partition by student_number, _dbt_source_project
                    order by eligibility_start_date
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
                partition by student_number, _dbt_source_project
                order by eligibility_start_date
            ) as island_id,
        from nj_flagged
    ),

    nj_leg as (
        select
            student_number,
            _dbt_source_project,
            eligibility_name as meal_eligibility,
            min(eligibility_start_date) as effective_date_start,
            coalesce(
                max(eligibility_end_date), date '9999-12-31'
            ) as effective_date_end,
        from nj_islanded
        group by student_number, _dbt_source_project, eligibility_name, island_id
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

    pm_anchor as (
        select
            student_number, _dbt_source_project, min(entrydate) as effective_date_start,
        from {{ ref("base_powerschool__student_enrollments") }}
        where region in ('Paterson', 'Miami')
        group by student_number, _dbt_source_project
    ),

    pm_leg as (
        select
            r.student_number,
            r._dbt_source_project,

            anchor.effective_date_start,

            date '9999-12-31' as effective_date_end,

            coalesce(r.lunch_status, 'Unknown') as meal_eligibility,
        from pm_recent as r
        inner join
            pm_anchor as anchor
            on r.student_number = anchor.student_number
            and r._dbt_source_project = anchor._dbt_source_project
        where r.region in ('Paterson', 'Miami')
    ),

    unioned as (
        select
            student_number,
            _dbt_source_project,
            meal_eligibility,
            effective_date_start,
            effective_date_end,
        from nj_leg
        union all
        select
            student_number,
            _dbt_source_project,
            meal_eligibility,
            effective_date_start,
            effective_date_end,
        from pm_leg
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as meal_eligibility_status_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    _dbt_source_project,
    meal_eligibility,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    meal_eligibility in ('F', 'R', 'FDC') as is_meal_eligible,
    effective_date_end = date '9999-12-31' as is_current,
from unioned
