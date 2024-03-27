with
    goals as (
        select
            gt.tag_id as goal_tag_id,
            gt.name as goal_tag_name,

            gt2.name as tag_name,

            regexp_extract(gt.name, r'^(\d[A-Z]\.\d+)') as goal_code,
            regexp_extract(gt.name, r'^(\d[A-Z])\.\d+') as strand_code,
            regexp_extract(gt.name, r'^(\d)[A-Z]\.\d+') as bucket_code,
        from {{ ref("stg_schoolmint_grow__generic_tags") }} as gt
        cross join unnest(gt.tags) as t
        left join
            {{ ref("stg_schoolmint_grow__generic_tags") }} as gt2 on t = gt2.tag_id
        where gt.type = 'goal'
    ),

    goals_parsed as (
        select
            goal_tag_id,
            goal_tag_name,
            goal_code,

            max(if(starts_with(tag_name, goal_code), tag_name, null)) as goal_name,
            max(
                if(starts_with(tag_name, strand_code || ':'), tag_name, null)
            ) as strand_name,
            max(
                if(starts_with(tag_name, bucket_code || ':'), tag_name, null)
            ) as bucket_name,
        from goals
        group by goal_tag_id, goal_tag_name, goal_code
    )

select
    goal_tag_id,
    bucket_name,
    strand_name,
    goal_code,
    goal_name,

    regexp_replace(goal_tag_name, goal_name || r'\s+', '') as goal_description,
from goals_parsed
