select
    *,

    case
        expected_score_type
        when 'sat_total_score'
        then 'Combined'
        when 'sat_ebrw'
        then 'EBRW'
        when 'sat_math'
        then 'Math'
    end as expected_subject_area,

from {{ source("google_sheets", "src_google_sheets__kippfwd_expected_assessments") }}
