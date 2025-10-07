with
    goals as (
        select
            gt.tag_id as base_tag_id,
            gt.name as base_tag_name,

            t as tag_id,

            gt2.name as tag_name,

            coalesce(
                regexp_extract(gt.name, r'^(\d[A-Z]\.\d+)'),
                regexp_extract(gt.name, r'^([^-]+-[^-]+-\d+)')
            ) as goal_code,

            coalesce(
                regexp_extract(gt.name, r'^(\d[A-Z]).\d+'),
                regexp_extract(gt.name, r'^([^-]+-[^-]+)')
            ) as strand_code,

            coalesce(
                regexp_extract(gt.name, r'^(\d)[A-Z].\d+'),
                regexp_extract(gt.name, r'^([^-]+)')
            ) as bucket_code,
        from {{ ref("stg_schoolmint_grow__generic_tags") }} as gt
        cross join unnest(gt.tags) as t
        left join
            {{ ref("stg_schoolmint_grow__generic_tags") }} as gt2 on t = gt2.tag_id
        where gt.type = 'goal'
    ),

    goals_parsed as (
        select
            base_tag_id,
            base_tag_name,
            goal_code,

            max(
                if(starts_with(tag_name, goal_code), tag_id, base_tag_id)
            ) as goal_tag_id,
            max(
                if(starts_with(tag_name, goal_code), tag_name, base_tag_name)
            ) as goal_name,
            max(
                if(starts_with(tag_name, strand_code || ':'), tag_name, strand_code)
            ) as strand_name,
            max(
                if(starts_with(tag_name, bucket_code || ':'), tag_name, bucket_code)
            ) as bucket_name,
        from goals
        group by base_tag_id, base_tag_name, goal_code
    )

select
    base_tag_id,
    base_tag_name,
    goal_tag_id,
    goal_name,
    goal_code,
    strand_name,
    bucket_name,

    regexp_replace(
        base_tag_name, replace(replace(goal_name, '(', r'\('), ')', r'\)') || r'\s+', ''
    ) as goal_description,
from goals_parsed
