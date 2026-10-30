with
    scored as (
        select
            a.assessment_id,
            a.contact_id,
            a.assessed_at,
            a.assessed_by,
            a.career_ready_level,
            a.active_search_level,
            a.internship_experience_level,
            a.network_level,
            a.coaching_focus,
            a.next_action,
            a.notes,

            cr.points as career_ready_points,

            ac.points as active_search_points,

            ie.points as internship_experience_points,

            nw.points as network_points,

            coalesce(c.gpa_points, 0) as gpa_points,

            coalesce(cr.points, 0)
            + coalesce(ac.points, 0)
            + coalesce(ie.points, 0)
            + coalesce(nw.points, 0)
            + coalesce(c.gpa_points, 0) as launch_score,

            if(
                a.career_ready_level is not null
                and a.active_search_level is not null
                and a.internship_experience_level is not null
                and a.network_level is not null,
                true,
                false
            ) as has_all_levels,
        from
            {{ ref("stg_google_appsheet__kfwd_career_conversations__assessments") }}
            as a
        left join
            {{ ref("stg_google_sheets__kfwd__career_launch_rubric") }} as cr
            on a.career_ready_rubric_key = cr.rubric_key
        left join
            {{ ref("stg_google_sheets__kfwd__career_launch_rubric") }} as ac
            on a.active_search_rubric_key = ac.rubric_key
        left join
            {{ ref("stg_google_sheets__kfwd__career_launch_rubric") }} as ie
            on a.internship_experience_rubric_key = ie.rubric_key
        left join
            {{ ref("stg_google_sheets__kfwd__career_launch_rubric") }} as nw
            on a.network_rubric_key = nw.rubric_key
        left join
            {{ ref("int_surveys__kfwd_career_launch_contacts") }} as c
            on a.contact_id = c.contact_id
    ),

    stages as (
        select
            stage,
            min_score,

            coalesce(
                lead(min_score) over (order by min_score), cast('inf' as float64)
            ) as max_score,
        from {{ ref("stg_google_sheets__kfwd__career_launch_stages") }}
    )

select
    sc.assessment_id,
    sc.contact_id,
    sc.assessed_at,
    sc.assessed_by,
    sc.career_ready_level,
    sc.active_search_level,
    sc.internship_experience_level,
    sc.network_level,
    sc.coaching_focus,
    sc.next_action,
    sc.notes,
    sc.career_ready_points,
    sc.active_search_points,
    sc.internship_experience_points,
    sc.network_points,
    sc.gpa_points,
    sc.launch_score,
    sc.has_all_levels,

    st.stage as launch_stage,

    row_number() over (
        partition by sc.contact_id order by sc.assessed_at desc, sc.assessment_id desc
    )
    = 1 as is_latest_assessment,
from scored as sc
left join
    stages as st on sc.launch_score >= st.min_score and sc.launch_score < st.max_score
