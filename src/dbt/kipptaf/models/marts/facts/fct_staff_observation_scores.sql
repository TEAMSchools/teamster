with
    scores as (
        select
            obs.observation_id,
            obs.rubric_id,

            os.measurement as measurement_id,
            os.measurementgroup as measurement_group_id,
            os.valuescore as value_score,
            os.valuetext as value_text,
            os.percentage,

            nullif(
                array_to_string(
                    array(
                        select
                            regexp_replace(
                                regexp_replace(tb.value, r'<[^>]*>', ''), r'&nbsp;', ' '
                            )
                        from unnest(os.textboxes) as tb
                        where tb.value is not null and tb.value != ''
                    ),
                    '; '
                ),
                ''
            ) as text_box_content,

            nullif(
                array_to_string(
                    array(
                        select cb.label from unnest(os.checkboxes) as cb where cb.value
                    ),
                    ', '
                ),
                ''
            ) as checkbox_values,
        from {{ ref("stg_schoolmint_grow__observations") }} as obs
        left join unnest(obs.observation_scores) as os
        where
            obs.is_published
            and os.measurement is not null
            and obs.observation_id
            in (select observation_id from {{ ref("fct_staff_observations") }})
    )

select
    {{ dbt_utils.generate_surrogate_key(["observation_id", "measurement_id"]) }}
    as staff_observation_score_key,

    {{ dbt_utils.generate_surrogate_key(["observation_id"]) }} as staff_observation_key,

    {{ dbt_utils.generate_surrogate_key(["rubric_id", "measurement_id"]) }}
    as staff_observation_rubric_measurement_key,

    observation_id,
    measurement_id,
    measurement_group_id,
    value_score,
    value_text,
    percentage,
    text_box_content,
    checkbox_values,
from scores
