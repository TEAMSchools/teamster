select
    *,

    case
        when expected_score_type like '%total%'
        then 'Combined'
        when expected_score_type like '%ebrw%'
        then 'EBRW'
        when expected_score_type like '%math%'
        then 'Math'
    end as expected_subject_area,

from {{ source("google_sheets", "src_google_sheets__kippfwd_expected_assessments") }}
