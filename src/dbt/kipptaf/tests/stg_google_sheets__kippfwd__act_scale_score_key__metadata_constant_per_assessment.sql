-- int_assessments__college_assessment_practice designates an assessment by
-- inner-joining a `select distinct assessment_id, academic_year, test_type,
-- administration_round, subject, grade_level` list built from this sheet. That
-- distinct collapses to one row per assessment ONLY while those five attributes
-- never vary within an assessment_id. If a data-entry error makes any of them
-- vary, the distinct yields two rows for that assessment and the designation
-- join fans every one of its response rows out, silently doubling scores and
-- composites. Fails on any assessment_id carrying more than one metadata
-- combination.
select assessment_id, count(distinct metadata_combination) as metadata_combinations,
from
    (
        select
            assessment_id,

            format(
                '%T|%T|%T|%T|%T',
                academic_year,
                test_type,
                administration_round,
                `subject`,
                grade_level
            ) as metadata_combination,
        from {{ ref("stg_google_sheets__kippfwd__act_scale_score_key") }}
    )
group by assessment_id
having count(distinct metadata_combination) > 1
