with
    /*
        TODO: remove this deduplication once the duplicate kippadb standardized
        test records are cleaned up at source. 87 SAT sittings are entered twice
        in Salesforce -- two distinct record ids sharing contact, date, and score
        -- which reaches this model as byte-identical rows and double-weights
        those scores in the workbook's averages. Deduplicating here fixes the
        average-score views only; the same source duplication still inflates
        attempt counts wherever the official hub is counted with `count(*)`.
    */
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    scores as (
        select
            s.student_number,
            s.test_type,
            s.scope,
            s.score_type,
            s.subject_area,
            s.aligned_subject_area,
            s.test_date,
            s.scale_score,
            s.max_scale_score,

            e.region,
            e.school,
            e.graduation_year,
            e.ktc_cohort,

        from {{ ref("int_assessments__all_college_assessments") }} as s
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on s.student_number = e.student_number
            and e.school_level = 'HS'
            and e.rn_undergrad = 1
            and e.rn_year = 1
            and not e.is_out_of_district
        where
            s.score_type not in (
                'act_english',
                'act_science',
                'psat10_math_test',
                'psat10_reading',
                'sat_math_test_score',
                'sat_reading_test_score'
            )
    ),

    deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="scores",
                partition_by="student_number, test_type, score_type, test_date, scale_score",
                order_by="max_scale_score desc",
            )
        }}
    )

select
    student_number,
    test_type,
    scope,
    score_type,
    subject_area,
    aligned_subject_area,
    test_date,
    scale_score,
    max_scale_score,
    region,
    school,
    graduation_year,
    ktc_cohort,

from deduplicated
