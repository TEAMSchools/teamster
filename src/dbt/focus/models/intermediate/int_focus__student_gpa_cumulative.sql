with
    gpa_ranked as (
        select
            id,
            student_id,
            school_id,
            syear,
            class_rank,
            cumulative_gpa,
            cumulative_weighted_gpa,
            cumulative_credits,

            row_number() over (
                partition by student_id, school_id order by syear desc, id desc
            ) as rn_syear,
        from {{ ref("stg_focus__student_gpa_calculated") }}
        where marking_period_id = -1
    )

select
    id,
    student_id,
    school_id,
    syear,
    class_rank,
    cumulative_gpa,
    cumulative_weighted_gpa,
    cumulative_credits,
from gpa_ranked
where rn_syear = 1
