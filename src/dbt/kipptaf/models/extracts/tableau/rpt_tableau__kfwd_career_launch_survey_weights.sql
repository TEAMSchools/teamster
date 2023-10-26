with
    survey_data as (
        select
            question_title_english,
            question_short_name,
            cast(response_string_value as numeric) as response_numeric_value,
        from {{ ref("base_alchemer__survey_results") }}
        where
            survey_id = 6734664
            and question_short_name in (
                'imp_1',
                'imp_2',
                'imp_3',
                'imp_4',
                'imp_5',
                'imp_6',
                'imp_7',
                'imp_8',
                'imp_9',
                'imp_10'
            )
    ),

    weight_denominator as (
        select sum(response_numeric_value) as answer_total, from survey_data
    ),

    score_weights as (
        select
            s.question_short_name,
            s.question_title_english,

            (sum(s.response_numeric_value) / a.answer_total) * 10.0 as item_weight,
        from survey_data as s
        cross join weight_denominator as a
        group by s.question_short_name, s.question_title_english, a.answer_total
    ),

    avg_scores as (
        select question_short_name, avg(response_numeric_value) as avg_weighted_scores,
        from survey_data
        group by question_short_name
    )

select
    s.question_short_name,
    s.avg_weighted_scores,

    w.question_title_english as question_title,
    w.item_weight / 10.0 as percent_weight,
from avg_scores as s
inner join score_weights as w on s.question_short_name = w.question_short_name
