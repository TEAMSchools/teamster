select
    *,

    safe_cast(right(test_code, 1) as int) as round_number,

    regexp_extract(measure_standard, r'^[^_]*') as expected_measure_name_code,
    regexp_substr(measure_standard, r'_(.*?)_') as expected_measure_name,
    regexp_substr(measure_standard, r'[^_]+$') as expected_measure_standard,

    if(grade = 0, 'K', cast(grade as string)) as grade_level_text,

    if(admin_season in ('BOY', 'MOY', 'EOY'), 'Benchmark', 'PM') as assessment_type,

    case
        admin_season when 'BOY' then 'BOY->MOY' when 'MOY' then 'MOY->EOY'
    end as matching_pm_season,

from {{ source("google_sheets", "src_google_sheets__dibels_expected_assessments") }}
