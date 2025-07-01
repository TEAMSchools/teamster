with
    modified as (
        select
            *,

            case
                admin_season when 'BOY' then 'BOY->MOY' when 'MOY' then 'MOY->EOY'
            end as matching_pm_season,

            regexp_extract(
                measure_standard, r'^[^_]*'
            ) as expected_mclass_measure_name_code,

            regexp_substr(measure_standard, r'_(.*?)_') as expected_mclass_measure_name,

            regexp_substr(
                measure_standard, r'[^_]+$'
            ) as expected_mclass_measure_standard,

            if(grade = 0, 'K', safe_cast(grade as string)) as grade_level_text,

            safe_cast(right(test_code, 1) as int64) as `round`,

        from
            {{
                source(
                    "google_sheets", "src_google_sheets__dibels_expected_assessments"
                )
            }}
    )

select
    *,

    min(round) over (
        partition by academic_year, region, admin_season, grade order by `round`
    ) as min_pm_round,

    max(`round`) over (
        partition by academic_year, region, admin_season, grade order by `round` desc
    ) as max_pm_round,

from modified
