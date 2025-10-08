with
    tags as (
        select
            _id as tag_id,
            name as tag_name,
            cast(parents[safe_offset(0)] as string) as parent_id,
        from {{ ref("stg_schoolmint_grow__src_schoolmint_grow__generic_tags_tags") }}
        where archivedat is null
    ),
    {# joining to parent ids for three levels (max in Grow) #}
    hierarchy as (
        select
            tags.tag_id,
            tags.tag_name,
            parent_1.tag_name as strand_name,
            parent_2.tag_name as bucket_name,
            parent_3.tag_name as goal_type_name,
        from tags
        left join tags as parent_1 on tags.parent_id = parent_1.tag_id
        left join tags as parent_2 on parent_1.parent_id = parent_2.tag_id
        left join tags as parent_3 on parent_2.parent_id = parent_3.tag_id
    )
{# only including goals with 3 levels above to get base microgoals and #}
{# lookfors and not hierarchy tags #}
select tag_id, tag_name, strand_name, bucket_name, goal_type_name,
from hierarchy
where goal_type_name is not null
