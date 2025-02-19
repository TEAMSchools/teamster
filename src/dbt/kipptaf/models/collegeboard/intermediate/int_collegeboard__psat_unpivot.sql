with
    psat as (
        select
            cb_id,
            powerschool_student_number as local_student_id,

            score,

            concat(
                test_name, '_', regexp_extract(score_type, r'^[^_]+_(.+)')
            ) as score_type,

            safe_cast(latest_psat_date as date) as `date`,

            case
                test_type
                when 'PSATNM'
                then 'PSAT NMSQT'
                when 'PSAT89'
                then 'PSAT 8/9'
                when 'PSAT10'
                then 'PSAT10'
            end as test_type,

            case
                score_type
                when 'latest_psat_total'
                then 'Composite'
                when 'latest_psat_math_section'
                then 'Math'
                when 'latest_psat_ebrw'
                then 'EBRW'
            end as test_subject,

        from
            {{ ref("int_collegeboard__psat") }} unpivot (
                score for score_type
                in (latest_psat_total, latest_psat_math_section, latest_psat_ebrw)
            )
    )

select
    cb_id,
    local_student_id,
    `date`,
    score_type,
    score,
    test_type,
    test_subject,

    row_number() over (
        partition by local_student_id, test_type, score_type order by score desc
    ) as rn_highest,
from psat
