with
    unpivoted as (
        select
            id,
            contact,
            school_specific_id,
            academic_year,
            administration_round,
            `date`,
            test_type,

            score_type,
            score,

            case
                when
                    score_type in (
                        'act_reading',
                        'act_english',
                        'sat_reading_test_score',
                        'sat_ebrw'
                    )
                then 'ENG'
                when score_type in ('act_math', 'sat_math_test_score', 'sat_math')
                then 'MATH'
            end as course_discipline,

            if(
                test_type = 'Advanced Placement',
                `subject`,
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
                            end,
                        from unnest(split(score_type, '_')) as component
                        where
                            component not in (
                                'act',
                                'sat',
                                'ap',
                                'pre',
                                '2016',
                                'critical',
                                'score',
                                'psat'
                            )
                    ),
                    ' '
                )
            ) as test_subject,

            row_number() over (
                partition by contact, test_type, score_type order by score desc
            ) as rn_highest,
        from
            {{ ref("int_kippadb__standardized_test") }} unpivot (
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
                    psat_critical_reading_pre_2016,
                    psat_ebrw,
                    psat_math_pre_2016,
                    psat_math_test_score,
                    psat_math,
                    psat_reading_test_score,
                    psat_total_score,
                    psat_verbal,
                    psat_writing_and_language_test_score,
                    psat_writing_pre_2016,
                    psat_writing,
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
        where
            test_type in ('ACT', 'Advanced Placement', 'PSAT', 'SAT')
            and not scoring_irregularity
    )

select
    *,

    case
        score_type
        when 'sat_total_score'
        then 'Combined'
        when 'psat_total_score'
        then 'Combined'
        when 'sat_reading_test_score'
        then 'Reading Test'
        when 'sat_math_test_score'
        then 'Math Test'
        else test_subject
    end as subject_area,
from unpivoted
