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
    ),

    final as (
        select
            b.powerschool_student_number,
            b.sat_date,
            b.test_type,
            b.score_type,
            b.score,

            e.salesforce_contact_id,

        from base_scores as b
        left join
            {{ ref("int_kippadb__standardized_test_unpivot") }} as sf
            on b.powerschool_student_number = sf.school_specific_id
            and b.score_type = sf.score_type
            and b.sat_date = sf.date
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on b.powerschool_student_number = e.student_number
            and e.rn_year = 1
            and e.rn_undergrad = 1
        where sf.date is null and e.salesforce_contact_id is not null
    )

select
    salesforce_contact_id as contact__c,
    sat_date as test_date__c,

    sat_total_score as sat_total,
    sat_ebrw,
    sat_math,

    test_type as test_type__c,

    '01280000000BQ2ZAAW' as recordtypeid,

from
    final
    pivot (avg(score) for score_type in ('sat_total_score', 'sat_ebrw', 'sat_math'))
