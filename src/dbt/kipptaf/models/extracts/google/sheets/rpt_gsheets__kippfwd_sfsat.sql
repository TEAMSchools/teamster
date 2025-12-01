with
    base_scores as (
        select
            powerschool_student_number,
            sat_date,
            test_type,

            case
                score_type
                when 'sat_total'
                then 'sat_total_score'
                when 'sat_math_section'
                then 'sat_math'
                else score_type
            end as score_type,
            score,

        from
            {{ ref("int_collegeboard__sat_unpivot") }}
            unpivot (score for score_type in (sat_ebrw, sat_math_section, sat_total))
    )

select
    b.powerschool_student_number,
    b.sat_date,
    b.test_type,
    b.score_type,
    b.score,

    sf.`date`,

from base_scores as b
left join
    {{ ref("int_kippadb__standardized_test_unpivot") }} as sf
    on b.powerschool_student_number = sf.school_specific_id
    and b.score_type = sf.score_type
where sf.`date` is null
