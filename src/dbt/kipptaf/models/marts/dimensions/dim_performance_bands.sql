select
    performance_band_key,
    performance_band_set,
    band_label,
    band_number,
    band_count,
    minimum_score,
    maximum_score,
    is_mastery,
    mastery_band_number,
    mastery_minimum_score,
    mastery_level,
    is_far_below,
from {{ ref("int_assessments__performance_band_union") }}
