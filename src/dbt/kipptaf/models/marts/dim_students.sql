with
    student_enrollments as (

        select * from {{ ref("base_powerschool__student_enrollments") }}
    ),

    final as (
        select
            student_number,
            studentid,
            schoolid,
            school_level,
            school_name,
            school_abbreviation,
            first_name,
            last_name,
            middle_name,
            region,
            school_level,
            spedlep,
            lep_status,
            is_504,
            is_self_contained,
            ethnicity,
            gender,
            academic_year,
            entrydate,
            exitdate,
        from student_enrollments
    )

select *,
from final
