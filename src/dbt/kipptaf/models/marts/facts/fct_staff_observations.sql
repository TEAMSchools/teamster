with
    observations_with_terms as (
        select
            o.observation_id,
            o.rubric_id,
            o.employee_number,
            o.observer_employee_number,
            o.academic_year,
            o.observed_at as observed_at_date,
            o.observed_at_timestamp,
            o.observation_score,
            o.overall_tier,
            o.glows,
            o.grows,
            o.locked,
            o.observation_notes,
            o.rubric_name,
            o.observation_type,
            o.observation_type_abbreviation,
            o.term_code,
            o.term_name,
            o.eval_date,

            lc.location_clean_name,
            lc.location_region,

            t.type as t_type,
            t.code as t_code,
            t.`name` as t_name,
            t.start_date as t_start_date,
            t.region as t_region,
            t.school_id as t_school_id,

            row_number() over (
                partition by o.observation_id order by t.`name` asc nulls last
            ) as rn,
        from {{ ref("int_performance_management__observations") }} as o
        left join
            {{ ref("int_schoolmint_grow__observations") }} as gro
            on o.observation_id = gro.observation_id
        left join
            {{ ref("int_people__location_crosswalk") }} as lc
            on gro.school_name = lc.location_name
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as t
            on o.observation_type_abbreviation = t.type
            and o.observed_at between t.start_date and t.end_date
            and lc.location_region = t.region
    )

select
    {{ dbt_utils.generate_surrogate_key(["observation_id"]) }} as staff_observation_key,

    {{ dbt_utils.generate_surrogate_key(["employee_number"]) }} as teacher_staff_key,

    {{ dbt_utils.generate_surrogate_key(["observer_employee_number"]) }}
    as observer_staff_key,

    {{ dbt_utils.generate_surrogate_key(["location_clean_name"]) }} as location_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "t_type",
                "t_code",
                "t_name",
                "t_start_date",
                "t_region",
                "t_school_id",
            ]
        )
    }} as term_key,

    observation_id,
    employee_number as teacher_employee_number,
    observer_employee_number,
    academic_year,

    observed_at_date,
    observed_at_timestamp,

    observation_score,
    overall_tier,
    glows,
    grows,
    locked,
    observation_notes,
    rubric_name,
    observation_type,
    observation_type_abbreviation,
    term_code,
    term_name,
    eval_date,
from observations_with_terms
where rn = 1
