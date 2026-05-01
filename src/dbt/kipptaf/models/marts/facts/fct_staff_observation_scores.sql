with
    scores as (
        select
            obs.observation_id,
            obs.rubric_id,

            os.measurement as measurement_id,
            os.valuescore as value_score,
            os.valuetext as value_text,

            nullif(
                array_to_string(
                    array(
                        select
                            regexp_replace(
                                regexp_replace(tb.value, r'<[^>]*>', ''), r'&nbsp;', ' '
                            ),
                        from unnest(os.textboxes) as tb
                        where tb.value is not null and tb.value != ''
                    ),
                    '; '
                ),
                ''
            ) as text_box_content,
        from {{ ref("stg_schoolmint_grow__observations") }} as obs
        left join unnest(obs.observation_scores) as os
        where
            obs.is_published
            and os.measurement is not null
            and {{ dbt_utils.generate_surrogate_key(["obs.observation_id"]) }} in (
                select fo.staff_observation_key,
                from {{ ref("fct_staff_observations") }} as fo
            )
    )

select
    {{ dbt_utils.generate_surrogate_key(["observation_id", "measurement_id"]) }}
    as staff_observation_score_key,

    {{ dbt_utils.generate_surrogate_key(["observation_id"]) }} as staff_observation_key,

    {{ dbt_utils.generate_surrogate_key(["rubric_id", "measurement_id"]) }}
    as staff_observation_rubric_measurement_key,

    text_box_content,

    value_score as score_value,
    value_text as response_text,
from scores
