with
    unpivoted as (
        select
            id,
            contact,
            last_modified_date,
            school_specific_id,
            academic_year,
            administration_round,
            test_type,
            score_type,
            score,

            if(`date` < date '2000-01-01', null, `date`) as `date`,

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
                when score_type = 'act_science'
                then 'SCI'
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
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    with_course as (
        select u.*, acc.ap_course_name, acc.ps_ap_course_subject_code,
        from unpivoted as u
        left join
            {{ ref("stg_google_sheets__collegeboard__ap_course_crosswalk") }} as acc
            on u.test_subject = acc.test_name
            and acc.data_source = 'ADB'
    ),

    /* an AP exam entered twice under 2 subject spellings keeps its latest edit */
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="with_course",
                partition_by="contact, test_type, score_type, ap_course_name, `date`",
                order_by="last_modified_date desc, id desc",
            )
        }}
    )

select
    id,
    contact,
    school_specific_id,
    academic_year,
    administration_round,
    test_type,
    score_type,
    score,
    `date`,
    course_discipline,
    test_subject,
    ap_course_name,
    ps_ap_course_subject_code,

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

    row_number() over (
        partition by contact, test_type, score_type, ap_course_name
        order by score desc, `date` desc, id asc
    ) as rn_highest,
from deduplicate
