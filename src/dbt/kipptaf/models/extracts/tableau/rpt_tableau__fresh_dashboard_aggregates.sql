with
    summary as (
        select
            _dbt_source_relation,
            academic_year,
            academic_year_display,
            enrollment_year,
            region,
            school,
            finalsite_student_id,
            grade_level,
            grade_level_string,
            week_start_monday,
            week_end_sunday,

            'KTAF' as org,

            max(offered_ops) as offered_ops,
            max(pending_offer_ops) as pending_offer_ops,
            max(overall_conversion_ops) as overall_conversion_ops,
            max(offers_to_accepted_num) as offers_to_accepted_num,
            max(offers_to_accepted_den) as offers_to_accepted_den,
            max(accepted_to_enrolled_num) as accepted_to_enrolled_num,
            max(accepted_to_enrolled_den) as accepted_to_enrolled_den,
            max(offers_to_enrolled_num) as offers_to_enrolled_num,
            max(offers_to_enrolled_den) as offers_to_enrolled_den,
            max(waitlisted) as waitlisted,

        from {{ ref("int_students__finalsite_student_roster") }}
        group by
            _dbt_source_relation,
            academic_year,
            academic_year_display,
            enrollment_year,
            region,
            school,
            finalsite_student_id,
            grade_level,
            grade_level_string,
            week_start_monday,
            week_end_sunday
    )

select *,
from summary
