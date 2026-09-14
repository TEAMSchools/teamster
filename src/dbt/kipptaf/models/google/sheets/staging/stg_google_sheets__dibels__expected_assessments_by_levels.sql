select
    *,

    safe_cast(regexp_extract(test_code, r'LIT(\d+)') as int) as round_number,

    regexp_extract(measure_standard, r'^[^_]*') as expected_measure_name_code,
    regexp_substr(measure_standard, r'_(.*?)_') as expected_measure_name,
    regexp_substr(measure_standard, r'[^_]+$') as expected_measure_standard,

    if(grade = 0, 'K', cast(grade as string)) as grade_level_text,

    case
        admin_season when 'BOY->MOY' then 'MOY' when 'MOY->EOY' then 'EOY'
    end as matching_bm_season,

from
    {{
        source(
            "google_sheets",
            "src_google_sheets__dibels__expected_assessments_by_levels",
        )
    }}
