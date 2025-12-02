with
    base_scores as (
        select
            powerschool_student_number,
            sat_date,
            test_type,

            score,

            case
                score_type
                when 'sat_total'
                then 'sat_total_score'
                when 'sat_math_section'
                then 'sat_math'
                else score_type
            end as score_type,

        from
            {{ ref("int_collegeboard__sat_unpivot") }}
            unpivot (score for score_type in (sat_ebrw, sat_math_section, sat_total))
    )

select
    b.sat_date as test_date,
    b.score,
    e.salesforce_id as contact_id,
    e.region,

    case
        b.score_type
        when 'sat_total_score'
        then 'New SAT'
        when 'sat_ebrw'
        then 'New SAT Reading and Writing'
        when 'sat_math'
        then 'New SAT Math'
    end as test,

from base_scores as b
left join
    {{ ref("int_kippadb__standardized_test_unpivot") }} as sf
    on b.powerschool_student_number = sf.school_specific_id
    and b.score_type = sf.score_type
    and b.sat_date = sf.`date`
left join
    {{ ref("int_extracts__student_enrollments") }} as e
    on b.powerschool_student_number = e.student_number
    and e.rn_year = 1
    and e.rn_undergrad = 1
where sf.`date` is null and e.salesforce_id is not null
