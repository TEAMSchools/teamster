with
    by_student as (
        select
            cohort,
            student_number,
            discipline,
            ps_grad_path_code,
            attempted_njgpa_ela,
            attempted_njgpa_math,

            countif(pathway_option = 'NJGPA' and scale_score is not null) as scored,
        from {{ ref("int_students__graduation_path_codes") }}
        /* DLM, portfolio, no-pathway and incomplete-credit students are coded
           straight from PowerSchool and never reach the cut score join. */
        where ps_grad_path_code is null or ps_grad_path_code not in ('M', 'N', 'O', 'P')
        group by
            cohort,
            student_number,
            discipline,
            ps_grad_path_code,
            attempted_njgpa_ela,
            attempted_njgpa_math
    ),

    attempted as (
        select
            cohort,
            student_number,
            discipline,
            scored,

            case
                when discipline = 'ELA'
                then attempted_njgpa_ela
                when discipline = 'Math'
                then attempted_njgpa_math
            end as sat_the_test,
        from by_student
    )

select cohort, student_number, discipline, scored,
from attempted
where sat_the_test and scored = 0
