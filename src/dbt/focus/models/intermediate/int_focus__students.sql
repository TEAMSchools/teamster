-- Staging columns plus their decoded custom-field labels. Drives from staging
-- and LEFT JOINs the pivot: BigQuery UNPIVOT drops entities whose unpivoted
-- columns are all null, so the pivot alone is not a complete entity spine.
select
    s.*,

    p.ethnicity_hispanic_or_latino_label,
    p.race_white_label,
    p.race_black_or_african_american_label,
    p.race_asian_label,
    p.sex_label,
    p.race_american_indian_or_alaska_native_label,
    p.race_native_hawaiian_or_other_pacific_islander_label,
    p.residence_county_label,
    p.language_label,
    p.ese_fefp_code_label,
    p.english_language_learner_pk_12_label,
    p.gifted_eligibility_label,
from {{ ref("stg_focus__students") }} as s
left join {{ ref("int_focus__students__pivot") }} as p on s.student_id = p.student_id
