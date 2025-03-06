with
    psat as (
        select
            cb_id,
            powerschool_student_number,
            birth_date,
            academic_year,
            latest_psat_date,
            administration_round,
            score,
            test_type,

            -- reason for proposed change: this concat creates names like
            -- psat10_psat_math_section. it seems a bit redundant.
            regexp_replace(
                concat(test_name, '_', regexp_extract(score_type, r'^[^_]+_(.+)')),
                '_psat_',
                '_'
            ) as score_type,

            case
                -- 3 to 4 digit score
                when score_type = 'latest_psat_total'
                then 'Combined'
                -- 3-digit score
                when score_type = 'latest_psat_ebrw'
                then 'EBRW'
                -- 2-digit score
                when score_type = 'latest_psat_reading'
                then 'Reading'
                -- 3-digit score
                when score_type = 'latest_psat_math_section'
                then 'Math'
                -- 2-digit score
                when score_type = 'latest_psat_math_test'
                then 'Math Test'
            end as test_subject,

            case
                when score_type in ('latest_psat_ebrw', 'latest_psat_reading')
                then 'ENG'
                when score_type in ('latest_psat_math_section', 'latest_psat_math_test')
                then 'MATH'
            end as course_discipline,
        from
            {{ ref("int_collegeboard__psat") }} unpivot (
                score for score_type in (
                    latest_psat_total,
                    latest_psat_math_section,
                    latest_psat_ebrw,
                    latest_psat_reading,
                    latest_psat_math_test
                )
            )
    )

select
    cb_id,
    powerschool_student_number,
    birth_date,
    academic_year,
    administration_round,
    latest_psat_date,
    test_type,
    test_subject,
    course_discipline,
    score_type,
    score,

    row_number() over (
        partition by powerschool_student_number, test_type, score_type
        order by score desc
    ) as rn_highest,
from psat
