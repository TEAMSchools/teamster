with
    scored as (
        select cohort, score_type, cutoff, scale_score,
        from {{ ref("int_students__graduation_path_codes") }}
        where scale_score is not null and cutoff > 0
    ),

    by_cutoff as (
        select
            cohort,
            score_type,
            cutoff,

            count(*) as scored_rows,
            max(scale_score) as max_scale_score,
        from scored
        group by cohort, score_type, cutoff
    )

select cohort, score_type, cutoff, scored_rows, max_scale_score,
from by_cutoff
where scored_rows >= 20 and max_scale_score < cutoff
