-- levels carry whole-number bounds with gaps (49, 50), so a band runs up to the
-- next band's minimum
select
    bl.band_set_id,
    bl.label,
    bl.min_score,

    bs.name as band_set_name,

    coalesce(
        lead(bl.min_score) over (partition by bl.band_set_id order by bl.min_score),
        1000000
    ) as upper_bound,

    row_number() over (
        partition by bl.band_set_id order by bl.min_score
    ) as label_number,

    -- bare comparison keeps null when the set has no Level 3 band
    bl.min_score >= min(if(bl.label = 'Level 3', bl.min_score, null)) over (
        partition by bl.band_set_id
    ) as is_mastery,
from {{ ref("stg_focus__apex_band_levels") }} as bl
-- Focus does not flag the levels of a deleted set
inner join {{ ref("stg_focus__apex_band_sets") }} as bs on bl.band_set_id = bs.id
