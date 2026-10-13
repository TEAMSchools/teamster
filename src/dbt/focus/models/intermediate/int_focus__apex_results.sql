with
    sessions_ranked as (
        select
            s.id as session_id,
            s.assessment_id,
            s.student_id as student_number,
            s.syear as academic_year,
            s.score_actual,
            s.score_max,

            date(s.completed_at, '{{ var("local_timezone") }}') as date_taken,

            row_number() over (
                partition by s.student_id, s.assessment_id
                order by s.completed_at desc, s.id desc
            ) as rn,
        from {{ ref("stg_focus__apex_sessions") }} as s
        -- drops attempts on deleted assignments
        inner join
            {{ ref("stg_focus__apex_assigned_assessments") }} as aa
            on s.assignment_id = aa.id
        where s.completed and s.discarded is not true and s.excused is not true
    ),

    sessions_picked as (
        select
            session_id,
            assessment_id,
            student_number,
            academic_year,
            date_taken,
            score_actual,
            score_max,
        from sessions_ranked
        where rn = 1
    ),

    standard_scores as (
        select
            sp.session_id,
            qs.standard_id,

            sum(r.score_actual) as points,
            sum(r.score_max) as points_possible,
        from sessions_picked as sp
        inner join
            {{ ref("stg_focus__apex_session_responses") }} as r
            on sp.session_id = r.session_id
        inner join
            {{ ref("stg_focus__apex_question_standards") }} as qs
            on r.question_id = qs.question_id
        where r.score_actual is not null
        group by sp.session_id, qs.standard_id
    ),

    scores as (
        select
            session_id,

            'overall' as response_type,

            assessment_id as response_type_id,

            cast(null as string) as response_type_code,
            cast(null as string) as response_type_description,
            cast(null as string) as response_type_root_description,

            score_actual as points,
            score_max as points_possible,
        from sessions_picked

        union all

        select
            ss.session_id,

            'standard' as response_type,

            ss.standard_id as response_type_id,

            st.short_name as response_type_code,
            st.title as response_type_description,

            sc.title as response_type_root_description,

            ss.points,
            ss.points_possible,
        from standard_scores as ss
        left join {{ ref("stg_focus__standards") }} as st on ss.standard_id = st.id
        left join
            {{ ref("stg_focus__standard_categories_1") }} as sc
            on st.category_1_id = sc.id
    ),

    scores_ratio as (
        select
            sp.student_number,
            sp.assessment_id,
            sp.session_id,
            sp.academic_year,
            sp.date_taken,

            s.response_type,
            s.response_type_id,
            s.response_type_code,
            s.response_type_description,
            s.response_type_root_description,
            s.points,
            s.points_possible,

            a.band_set_id as performance_band_set_id,

            round(safe_divide(s.points, s.points_possible) * 100, 1) as percent_ratio,
        from scores as s
        inner join sessions_picked as sp on s.session_id = sp.session_id
        left join
            {{ ref("int_focus__apex_assessments") }} as a
            on sp.assessment_id = a.assessment_id
    ),

    scores_percent as (
        select
            student_number,
            assessment_id,
            session_id,
            academic_year,
            date_taken,
            response_type,
            response_type_id,
            response_type_code,
            response_type_description,
            response_type_root_description,
            points,
            points_possible,
            performance_band_set_id,

            cast(percent_ratio as float64) as percent_correct,
        from scores_ratio
    ),

    -- levels carry whole-number bounds with gaps (49, 50), so a band runs up to
    -- the next band's minimum
    band_levels as (
        select
            band_set_id,
            label,
            min_score,

            row_number() over (
                partition by band_set_id order by min_score
            ) as label_number,

            coalesce(
                lead(min_score) over (partition by band_set_id order by min_score),
                1000000
            ) as upper_bound,
        from {{ ref("stg_focus__apex_band_levels") }}
    )

select
    sp.student_number,
    sp.assessment_id,
    sp.session_id,
    sp.academic_year,
    sp.date_taken,
    sp.response_type,
    sp.response_type_id,
    sp.response_type_code,
    sp.response_type_description,
    sp.response_type_root_description,
    sp.points,
    sp.points_possible,
    sp.percent_correct,
    sp.performance_band_set_id,

    bl.label as performance_band_label,
    bl.label_number as performance_band_label_number,

    case
        when bl.label in ('Level 3', 'Level 4', 'Level 5')
        then true
        when
            bl.label
            in ('Level 1', 'Level 2', 'Low 1', 'Low 2', 'Mid 1', 'High 1', 'High 2')
        then false
    end as is_mastery,
from scores_percent as sp
left join
    band_levels as bl
    on sp.performance_band_set_id = bl.band_set_id
    and sp.percent_correct >= bl.min_score
    and sp.percent_correct < bl.upper_bound
