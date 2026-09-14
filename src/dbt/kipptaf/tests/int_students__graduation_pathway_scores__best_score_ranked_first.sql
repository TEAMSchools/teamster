with
    by_score_type as (
        select
            student_number,
            score_type,

            max(met_pathway_cutoff) as any_met,
            max(if(rn_highest = 1, met_pathway_cutoff, null)) as top_ranked_met,
        from {{ ref("int_students__graduation_pathway_scores") }}
        where scale_score is not null
        group by student_number, score_type
    )

select student_number, score_type, any_met, top_ranked_met,
from by_score_type
where any_met and not top_ranked_met
