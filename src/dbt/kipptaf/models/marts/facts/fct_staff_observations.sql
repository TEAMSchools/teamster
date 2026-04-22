with
    observation_types as (
        select tag_id, abbreviation,
        from {{ ref("stg_schoolmint_grow__generic_tags") }}
        where tag_type = 'observationtypes' and archived_at is null
    ),

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

            lc.location_clean_name,
            lc.location_region,

            ot.tag_id as observation_type_tag_id,

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
            observation_types as ot on o.observation_type_abbreviation = ot.abbreviation
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

    if(
        observation_type_tag_id is not null,
        {{ dbt_utils.generate_surrogate_key(["observation_type_tag_id"]) }},
        cast(null as string)
    ) as staff_observation_type_key,

    if(
        rubric_id is not null,
        {{ dbt_utils.generate_surrogate_key(["rubric_id"]) }},
        cast(null as string)
    ) as staff_observation_rubric_key,

    academic_year,
    observation_score as score,
    overall_tier,
    observation_notes as notes,

    observed_at_date as observed_date,
    observed_at_timestamp as observed_timestamp,
    glows as positive_feedback,
    grows as growth_areas,
    locked as is_locked,
from observations_with_terms
where rn = 1
