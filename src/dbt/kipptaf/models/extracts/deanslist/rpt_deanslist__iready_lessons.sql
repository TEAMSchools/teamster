SELECT
    pl.student_id,
    pl.subject,
    t.name AS term,
    CAST(
        SUM(
            CASE
                WHEN pl.passed_or_not_passed = 'Passed' THEN 1
                ELSE 0
            END
        ) AS FLOAT64
    ) AS lessons_passed,
    CAST(
        COUNT(DISTINCT pl.lesson_id) AS FLOAT64
    ) AS total_lessons,
    ROUND(
        CAST(
            SUM(
                CASE
                    WHEN pl.passed_or_not_passed = 'Passed' THEN 1
                    ELSE 0
                END
            ) AS FLOAT64
        ) / CAST(COUNT(pl.lesson_id) AS FLOAT64),
        2
    ) * 100 AS pct_passed
FROM
    {{ ref('stg_iready__personalized_instruction_by_lesson') }} AS pl
INNER JOIN
    {{ ref('stg_people__location_crosswalk') }} AS sc
    ON (pl.school = sc.name)
INNER JOIN {{ ref('stg_reporting__terms') }} AS t
    ON (
        sc.powerschool_school_id = t.school_id
        AND CAST(LEFT(pl.academic_year, 4) AS INT64) = t.academic_year
        AND (
            PARSE_DATE(
                '%m/%d/%Y', pl.completion_date
            ) BETWEEN t.start_date AND t.end_date
        )
        AND t.type = 'RT'
    )
WHERE
    PARSE_DATE('%m/%d/%Y', pl.completion_date) >= DATE(
        {{ var("current_academic_year") }},
        7,
        1
    )
GROUP BY
    pl.student_id,
    pl.subject,
    t.name
