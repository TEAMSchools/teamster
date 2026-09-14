with
    compared as (
        select
            student_number,
            score_type,
            assessment_version,
            scale_score,
            cutoff,
            met_pathway_cutoff,
            points_short,

            points_short >= 0 as points_short_says_met,
        from {{ ref("int_students__graduation_pathway_scores") }}
        where cutoff is not null and scale_score is not null
    )

select
    student_number,
    score_type,
    assessment_version,
    scale_score,
    cutoff,
    met_pathway_cutoff,
    points_short,
from compared
where met_pathway_cutoff is distinct from points_short_says_met
