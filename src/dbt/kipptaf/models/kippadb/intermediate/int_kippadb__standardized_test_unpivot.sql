select
    id,
    contact,
    date,
    score_type,
    score,
    test_type,
    if(
        test_type = 'Advanced Placement',
        subject,
        array_to_string(
            array(
                select
                    case
                        when component in ('ela', 'ebrw', 'stem')
                        then upper(component)
                        when component = 'and'
                        then 'and'
                        when component = 'test'
                        then 'Subscore'
                        else initcap(component)
                    end
                from unnest(split(score_type, '_')) as component
                where
                    component
                    not in ('act', 'sat', 'ap', 'pre', '2016', 'critical', 'score')
            ),
            ' '
        )
    ) as test_subject,

    row_number() over (
        partition by contact, score_type order by score desc
    ) as rn_highest,
from
    {{ ref("stg_kippadb__standardized_test") }} unpivot (
        score for score_type in (
            act_composite,
            act_ela,
            act_english,
            act_math,
            act_reading,
            act_science,
            act_stem,
            act_writing,
            ap,
            sat_critical_reading_pre_2016,
            sat_ebrw,
            sat_essay_analysis,
            sat_essay_reading,
            sat_essay_writing,
            sat_math_pre_2016,
            sat_math_test_score,
            sat_math,
            sat_reading_test_score,
            sat_total_score,
            sat_verbal,
            sat_writing_and_language_test_score,
            sat_writing_pre_2016,
            sat_writing
        )
    ) as u
where not scoring_irregularity and test_type in ('SAT', 'ACT', 'Advanced Placement')
