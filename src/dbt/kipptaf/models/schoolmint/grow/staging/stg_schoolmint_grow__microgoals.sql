with
    goals as (
        select
            gt.tag_id as goal_tag_id,
            gt.name as goal_name,

            coalesce(
                regexp_extract(gt.name, r'^(\d[A-Z]\.\d+)'),
                regexp_extract(gt.name, r'^([^-]+-[^-]+-\d+)')
            ) as goal_code,

            coalesce(
                regexp_extract(gt.name, r'^(\d[A-Z]).\d+'),
                regexp_extract(gt.name, r'^([^-]+-[^-]+)')
            ) as strand_name,

            coalesce(
                regexp_extract(gt.name, r'^(\d)[A-Z].\d+'),
                regexp_extract(gt.name, r'^([^-]+)')
            ) as bucket_name,
            concat(gt.tag_id, ' ', gt.name) as goal_description,
        from {{ ref("stg_schoolmint_grow__generic_tags") }} as gt
        where gt.type = 'goal'
    )

select *,
from goals
