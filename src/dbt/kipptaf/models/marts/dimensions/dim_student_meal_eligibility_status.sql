{% set invalid_lunch_status = ["", "NoD", "1", "2"] %}

with
    -- Per-enrollment-stint PowerSchool enrollment range. One row per stint;
    -- multi-stint students get multiple dim rows per eligibility record, each
    -- clipped to its specific entry/exit window. Aggregating to min/max would
    -- span gaps between stints.
    enrollments as (
        select
            student_number,
            _dbt_source_relation,
            _dbt_source_project,
            academic_year,
            entrydate,
            lunchstatus,

            -- PowerSchool exitdate is half-open (first day AFTER stint).
            -- Subtract 1 day to get the inclusive last day so boundary-sharing
            -- stints don't produce overlapping inclusive ends in the dim.
            coalesce(
                date_sub(exitdate, interval 1 day), cast('9999-12-31' as date)
            ) as enrollment_end,
        from {{ ref("int_powerschool__student_enrollment_union") }}
        -- graduates carry NULL entry/exit as a placeholder row; drop them
        -- (no enrollment context to clip against).
        where entrydate is not null
    ),

    nj_unioned as (
        select
            _dbt_source_project,
            eligibility_name,
            eligibility_start_date,

            person_identifier as student_number,

            -- Titan ships ~14-month annual windows that overlap at academic-year
            -- boundaries (current year extends past Sept 30, next year begins
            -- before Aug 1). Trim each row's end to day-before-next-row's-start
            -- so cross-value transitions don't produce overlapping spans after
            -- island collapse. Coalesce the open-ended sentinel so nj_leg can
            -- use a plain max() without re-handling NULL.
            least(
                coalesce(eligibility_end_date, cast('9999-12-31' as date)),
                coalesce(
                    date_sub(
                        lead(eligibility_start_date) over (
                            partition by person_identifier, _dbt_source_project
                            order by eligibility_start_date
                        ),
                        interval 1 day
                    ),
                    cast('9999-12-31' as date)
                )
            ) as eligibility_end_date,

            lag(eligibility_name) over (
                partition by person_identifier, _dbt_source_project
                order by eligibility_start_date
            ) as prev_eligibility_name,
        from {{ ref("stg_titan__person_data") }}
        where eligibility_start_date is not null
    ),

    nj_flagged as (
        select *, if(eligibility_name = prev_eligibility_name, 0, 1) as is_island_start,
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

    nj_leg_raw as (
        select
            student_number,
            _dbt_source_project,
            eligibility_name as meal_eligibility,

            min(eligibility_start_date) as effective_date_start,
            max(eligibility_end_date) as effective_date_end,
        from nj_islanded
        group by student_number, _dbt_source_project, eligibility_name, island_id
    ),

    nj_leg as (
        select
            l.student_number,
            l._dbt_source_project,
            l.meal_eligibility,

            e._dbt_source_relation,
            e.academic_year,
            e.entrydate,

            greatest(l.effective_date_start, e.entrydate) as effective_date_start,
            least(l.effective_date_end, e.enrollment_end) as effective_date_end,
        from nj_leg_raw as l
        inner join
            enrollments as e
            on l.student_number = e.student_number
            and l._dbt_source_project = e._dbt_source_project
            and l.effective_date_start <= e.enrollment_end
            and l.effective_date_end >= e.entrydate
    ),

    pm_leg as (
        select
            e.student_number,
            e._dbt_source_project,
            e._dbt_source_relation,
            e.academic_year,
            e.entrydate,

            if(
                e.lunchstatus in unnest({{ invalid_lunch_status }}), null, e.lunchstatus
            ) as meal_eligibility,

            e.entrydate as effective_date_start,
            e.enrollment_end as effective_date_end,
        from enrollments as e
        where e._dbt_source_project in ('kipppaterson', 'kippmiami')
    ),

    unioned as (
        select
            student_number,
            _dbt_source_project,
            _dbt_source_relation,
            academic_year,
            entrydate,
            meal_eligibility,
            effective_date_start,
            effective_date_end,
        from nj_leg

        union all

        select
            student_number,
            _dbt_source_project,
            _dbt_source_relation,
            academic_year,
            entrydate,
            meal_eligibility,
            effective_date_start,
            effective_date_end,
        from pm_leg
    ),

    classified as (
        -- coalesce both NJ (titan, ~2 NULLs) and PM (lunchstatus NULL when
        -- invalid or no current eligibility) to a single 'Unknown' so the
        -- is_meal_eligible derivation never returns NULL.
        select *, coalesce(meal_eligibility, 'Unknown') as meal_eligibility_clean,
        from unioned
    )

select
    _dbt_source_project,

    meal_eligibility_clean as meal_eligibility,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as student_meal_eligibility_status_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_relation", "academic_year", "entrydate"]
        )
    }} as student_enrollment_key,

    meal_eligibility_clean in ('F', 'R', 'FDC') as is_meal_eligible,
    effective_date_end = '9999-12-31' as is_current,
from classified
