with
    assessments as (
        select
            assessment_id,
            title,
            academic_year_clean,
            creator_local_user_id,
            creator_username,
            creator_first_name,
            creator_last_name,
            creator_email_1,

            date(academic_year_clean, 7, 1) as academic_year_start_date,
        from {{ ref("int_illuminate__assessments") }}
        -- Illuminate holds 0 and 1 as junk academic years
        where academic_year_clean >= 2000
    )

select
    sa.student_assessment_id,
    sa.assessment_id,
    sa.date_taken,

    a.title,
    a.academic_year_clean,
    a.creator_local_user_id,
    a.creator_username,
    a.creator_first_name,
    a.creator_last_name,
    a.creator_email_1,
from {{ ref("stg_illuminate__dna_assessments__students_assessments") }} as sa
inner join assessments as a on sa.assessment_id = a.assessment_id
where sa.date_taken < a.academic_year_start_date
