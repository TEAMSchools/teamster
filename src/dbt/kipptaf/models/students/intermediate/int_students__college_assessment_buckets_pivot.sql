with
    buckets as (
        select
            student_number,
            academic_year,
            _dbt_source_project,
            iready_subject,

            -- seniors (grade 12) are not assigned buckets
            if(
                grade_level = 12 and bucket_store is null,
                'No Bucket Assigned',
                nj_student_tier
            ) as bucket,
        from {{ ref("int_extracts__student_enrollments_subjects") }}
        where rn_year = 1 and school_level = 'HS'
    )

select
    student_number,
    academic_year,
    _dbt_source_project,

    max(if(iready_subject = 'Reading', bucket, null)) as nj_student_tier_ela,
    max(if(iready_subject = 'Math', bucket, null)) as nj_student_tier_math,
from buckets
group by student_number, academic_year, _dbt_source_project
