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

            if(
                expected_score_type = 'sat_total_score_growth',
                'sat_total_score',
                expected_score_type
            ) as expected_score_type_aligned,

            regexp_extract(expected_month_round, r'^([^ ]+)') as expected_month,

        from
            {{
                source(
                    "google_sheets", "src_google_sheets__kippfwd_expected_assessments"
                )
            }}
        where expected_admin_season != 'Not Official'
    ),

    months as (
        select
            expected_region,
            expected_grade_level,
            expected_test_type,
            expected_scope,
            expected_admin_season,

<<<<<<< HEAD
            string_agg(expected_month, ', ') as expected_months_included,

        from scores
        where
            expected_score_type like '%total%'
            and expected_score_type not like '%growth%'
=======
            string_agg(expected_month_round, ', ') as expected_months_included,

        from scores
        where expected_grouping = 'Total'
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
        group by
            expected_region,
            expected_grade_level,
            expected_test_type,
            expected_scope,
            expected_admin_season
    )

select
    s.*,

    m.expected_months_included,

    concat(
        'G',
        s.expected_grade_level,
        ' ',
        s.expected_admin_season,
        ' ',
        s.expected_test_type,
        ' ',
        s.expected_scope,
        ' ',
        s.expected_grouping
    ) as expected_field_name,

<<<<<<< HEAD
=======
    if(
        s.expected_grouping = 'Growth', 'Growth Score Change', 'Scale Score'
    ) as expected_score_category,

    row_number() over (
        partition by
            s.expected_region,
            s.expected_grade_level,
            s.expected_test_type,
            s.expected_score_type,
            s.expected_admin_season
        order by s.expected_admin_season_order
    ) as rn,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "s.expected_test_type",
                "s.expected_score_type_aligned",
                "s.expected_grade_level",
                "s.expected_admin_season",
            ]
        )
    }} as expected_unique_test_admin_id,

>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
from scores as s
left join
    months as m
    on s.expected_region = m.expected_region
    and s.expected_grade_level = m.expected_grade_level
    and s.expected_test_type = m.expected_test_type
    and s.expected_scope = m.expected_scope
    and s.expected_admin_season = m.expected_admin_season
