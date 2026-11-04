with
    question_subjects as (
        select
            ai.assessment_id,

            case
                when starts_with(sc.title, 'Language Arts')
                then 'Text Study'
                when starts_with(sc.title, 'Mathematics')
                then 'Mathematics'
                when starts_with(sc.title, 'Science')
                then 'Science'
                when starts_with(sc.title, 'Social Studies')
                then 'Social Studies'
            end as subject_area,
        from {{ ref("stg_focus__apex_assessment_items") }} as ai
        inner join
            {{ ref("stg_focus__apex_item_questions") }} as iq on ai.item_id = iq.item_id
        inner join
            {{ ref("stg_focus__apex_question_standards") }} as qs
            on iq.question_id = qs.question_id
        inner join {{ ref("stg_focus__standards") }} as s on qs.standard_id = s.id
        inner join
            {{ ref("stg_focus__standard_categories_1") }} as sc
            on s.category_1_id = sc.id
    ),

    question_subjects_keyed as (
        select
            assessment_id,
            subject_area,

            coalesce(subject_area, 'unmapped') as subject_key,
        from question_subjects
    ),

    -- an assessment spanning 2 subjects, or an unmapped category, gets none
    assessment_subjects as (
        select
            assessment_id,

            if(
                count(distinct subject_key) = 1, max(subject_area), null
            ) as subject_area,
        from question_subjects_keyed
        group by assessment_id
    ),

    -- deletes do not cascade to the link table
    band_sets as (
        select bsa.assessment_id, bsa.band_set_id,
        from {{ ref("stg_focus__apex_band_set_assessments") }} as bsa
        inner join
            {{ ref("stg_focus__apex_band_sets") }} as bs on bsa.band_set_id = bs.id
    ),

    assignments as (
        select
            assessment_id,

            min(start_date) as administered_at,

            -- school year rolls over on 1 July
            if(
                extract(month from min(start_date)) >= 7,
                extract(year from min(start_date)),
                extract(year from min(start_date)) - 1
            ) as administered_school_year,
        from {{ ref("stg_focus__apex_assigned_assessments") }}
        group by assessment_id
    )

select
    a.id as assessment_id,
    a.title,

    bs.band_set_id,

    sub.subject_area,

    asg.administered_at,

    -- some assessments carry no syear in Focus
    coalesce(a.syear, asg.administered_school_year) as academic_year,
from {{ ref("stg_focus__apex_assessments") }} as a
left join band_sets as bs on a.id = bs.assessment_id
left join assessment_subjects as sub on a.id = sub.assessment_id
left join assignments as asg on a.id = asg.assessment_id
