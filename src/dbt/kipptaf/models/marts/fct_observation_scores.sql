with
    scores as (
        select
            od.observation_id,
            od.measurement_id,
            od.measurement_name,
            od.strand_name,
            od.row_score,
            od.measurement_comments,
            drm.rubric_measurement_key,

            {# Use measurement_id when available (2024+ data); fall back to name for archive #}
            coalesce(od.measurement_id, od.measurement_name) as measurement_key_value,
        from {{ ref("int_performance_management__observation_details") }} as od
        left join
            {{ ref("dim_observation_rubric_measurement") }} as drm
            on od.rubric_id = drm.rubric_id
            and od.measurement_name = drm.measurement_name
            and od.strand_name = drm.strand_name
        where od.measurement_name is not null
        qualify
            row_number() over (
                partition by
                    od.observation_id, coalesce(od.measurement_id, od.measurement_name)
                order by od.observed_at nulls last
            )
            = 1
    )

select
    observation_id,
    measurement_id,
    row_score,

    regexp_replace(measurement_comments, r'<[^>]+>', '') as measurement_comments,

    rubric_measurement_key,

    {{ dbt_utils.generate_surrogate_key(["observation_id"]) }} as observation_key,

    {{ dbt_utils.generate_surrogate_key(["observation_id", "measurement_key_value"]) }}
    as observation_score_key,
from scores
