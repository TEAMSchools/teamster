with
    psat as (
        select
            cb_id,
            powerschool_student_number,
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
                score_type
                when 'latest_psat_total'
                then 'Composite'
                when 'latest_psat_math_section'
                then 'Math'
                when 'latest_psat_ebrw'
                then 'EBRW'
            end as test_subject,

            case
                score_type
                when 'latest_psat_ebrw'
                then 'ENG'
                when 'latest_psat_math_section'
                then 'MATH'
            end as course_discipline,
        from
            {{ ref("int_collegeboard__psat") }} unpivot (
                score for score_type
                in (latest_psat_total, latest_psat_math_section, latest_psat_ebrw)
            )
    )

select
    cb_id,
    powerschool_student_number,
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
