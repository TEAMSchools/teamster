with
    checked as (
        select
            student_number,
            discipline,
            score_type,
            assessment_version,

            count(distinct cutoff) as distinct_cutoffs,
        from {{ ref("int_students__graduation_pathway_scores") }}
        group by student_number, discipline, score_type, assessment_version
    )

select student_number, discipline, score_type, assessment_version, distinct_cutoffs,
from checked
where distinct_cutoffs > 1
