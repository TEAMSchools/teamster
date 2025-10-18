with
    scores as (
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

            regexp_extract(expected_month_round, r'^([^ ]+)') as expected_month,

        from
            {{
                source(
                    "google_sheets", "src_google_sheets__kippfwd_expected_assessments"
                )
            }}
    )

select
    *,

    case
        when expected_scope = 'SAT'
        then
            concat(
                'SY',
                right(cast(expected_academic_year as string), 2),
                ' ',
                expected_test_type,
                ' ',
                expected_scope,
                ' ',
                expected_subject_area,
                ' ',
                expected_admin_season
            )
    end as expected_field_name,

from scores
