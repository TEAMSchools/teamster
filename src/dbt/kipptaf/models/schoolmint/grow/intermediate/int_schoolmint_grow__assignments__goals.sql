with
    tags as (
        select
            tag_id,
            `name` as tag_name,

            cast(parents[safe_offset(0)] as string) as parent_id,
        from {{ ref("stg_schoolmint_grow__generic_tags") }}
        where archived_at is null and tag_type = 'tags'
    ),

    tag_paths as (
        select
            t.tag_id,
            t.tag_name,

            p1.tag_name as parent_1_name,

            p2.tag_name as parent_2_name,

            coalesce(p3.tag_name, p2.tag_name, p1.tag_name, t.tag_name) as root_name,

            case
                when p3.tag_id is not null
                then 3
                when p2.tag_id is not null
                then 2
                when p1.tag_id is not null
                then 1
                else 0
            end as depth,
        from tags as t
        /* Grow tag trees are at most three levels below their root */
        left join tags as p1 on t.parent_id = p1.tag_id
        left join tags as p2 on p1.parent_id = p2.tag_id
        left join tags as p3 on p2.parent_id = p3.tag_id
    ),

    assignment_tags as (
        select
            ast.assignment_id,

            tp.tag_id,
            tp.tag_name,
            tp.parent_1_name,
            tp.parent_2_name,
            tp.root_name,
            tp.depth,

            /* tree roots that hold goals: "Microgoals" and "Lookfors" */
            tp.root_name = 'Microgoals' and tp.depth = 3 as is_microgoal,
            tp.root_name = 'Lookfors' and tp.depth >= 1 as is_lookfor_category,
        from {{ ref("int_schoolmint_grow__assignments__tags") }} as ast
        inner join tag_paths as tp on ast.tag_id = tp.tag_id
    ),

    assignment_tags_ranked as (
        select
            assignment_id,
            tag_id,
            tag_name,
            parent_1_name,
            parent_2_name,
            root_name,
            depth,
            is_microgoal,
            is_lookfor_category,

            max(if(is_lookfor_category, depth, null)) over (
                partition by assignment_id
            ) as lookfor_max_depth,

            logical_or(is_microgoal) over (partition by assignment_id) as has_microgoal,
        from assignment_tags
    ),

    lookfor_candidates as (
        select
            assignment_id,
            tag_id,
            tag_name,
            parent_1_name,
            parent_2_name,
            root_name,
            depth,
            is_microgoal,

            /*
              a look-for's category is its most specific one; when the assignment
              holds a microgoal, its name is the microgoal's, so no look-for row
            */
            is_lookfor_category
            and depth = lookfor_max_depth
            and not has_microgoal as is_lookfor_candidate,
        from assignment_tags_ranked
    ),

    lookfor_picks as (
        select
            assignment_id,
            tag_id,
            tag_name,
            parent_1_name,
            parent_2_name,
            root_name,
            depth,
            is_microgoal,
            is_lookfor_candidate,

            /* two categories at the same depth: keep the alphabetically first */
            min(if(is_lookfor_candidate, tag_name, null)) over (
                partition by assignment_id
            ) as lookfor_category_name,
        from lookfor_candidates
    ),

    goal_tags as (
        select
            assignment_id,
            tag_id,
            tag_name,
            parent_1_name,
            parent_2_name,
            root_name,
            depth,
            is_microgoal,

            is_microgoal
            or (
                is_lookfor_candidate and tag_name = lookfor_category_name
            ) as is_goal_tag,
        from lookfor_picks
    ),

    microgoal_strands as (
        select tag_name, parent_1_name, root_name,
        from tag_paths
        where root_name = 'Microgoals' and depth = 2
    )

select
    a.assignment_id,
    a.user_id,
    a.creator_id,
    a.creator_name,
    a.created,
    a.created_date_local,

    g.tag_id as goal_tag_id,
    g.root_name as goal_type_name,

    if(g.is_microgoal, g.tag_name, a.name_text) as goal_name,
    if(g.is_microgoal, g.parent_1_name, g.tag_name) as strand_name,

    case
        when g.is_microgoal then g.parent_2_name when g.depth >= 2 then g.parent_1_name
    end as bucket_name,
from {{ ref("stg_schoolmint_grow__assignments") }} as a
inner join goal_tags as g on a.assignment_id = g.assignment_id and g.is_goal_tag

union all

select
    a.assignment_id,
    a.user_id,
    a.creator_id,
    a.creator_name,
    a.created,
    a.created_date_local,

    cast(null as string) as goal_tag_id,

    ms.root_name as goal_type_name,

    a.name_text as goal_name,

    ms.tag_name as strand_name,
    ms.parent_1_name as bucket_name,
from {{ ref("stg_schoolmint_grow__assignments") }} as a
left join goal_tags as g on a.assignment_id = g.assignment_id and g.is_goal_tag
left join
    microgoal_strands as ms
    on starts_with(ms.tag_name, concat(a.microgoal_strand_code, ':'))
where g.assignment_id is null
