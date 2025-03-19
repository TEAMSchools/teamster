select
    grade_level,
    has_fafsa,
    njgpa_season_11th,
    fafsa_season_12th,
    attempted_njgpa_ela,
    attempted_njgpa_math,
    met_ela,
    met_math,
    grad_eligibility,
from {{ source("reporting", "src_reporting__graduation_path_combos") }}