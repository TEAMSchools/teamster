with
    scores as (
        select
            *,

            case
                when expected_score_type like '%growth%'
                then 'Growth'
                when expected_score_type like '%total%'
                then 'Total'
                when expected_score_type like '%ebrw%'
                then 'EBRW'
                when expected_score_type like '%math%'
                then 'Math'
            end as expected_grouping,

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
        when expected_month_round = 'Year'
        then expected_month_round
        when expected_grouping = 'Growth'
        then
            'The previous month is based on the individual testing history for a student.'
        else
            string_agg(regexp_extract(expected_month_round, r'^([^ ]+)'), ', ') over (
                partition by
                    expected_region,
                    expected_grade_level,
                    expected_test_type,
                    expected_scope,
                    expected_admin_season
            )
    end as expected_months_included,

    concat(
        'G',
        cast(expected_grade_level as string),
        ' ',
        expected_admin_season,
        ' ',
        expected_test_type,
        ' ',
        expected_scope,
        ' ',
        expected_grouping
    ) as expected_field_name,

from scores
where expected_admin_season != 'Not Official'
