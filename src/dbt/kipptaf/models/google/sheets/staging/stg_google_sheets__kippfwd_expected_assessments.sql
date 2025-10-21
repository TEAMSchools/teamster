with
    scores as (
        select
            *,

            case
                when expected_score_type like '%growth%'
                then 'Total Growth'
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
        when expected_scope = 'SAT'
        then
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
            )
    end as expected_field_name,

from scores
where expected_admin_season != 'Not Official'
