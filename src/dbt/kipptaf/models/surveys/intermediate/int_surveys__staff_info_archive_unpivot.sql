select
    respondent_email,
    last_submitted_time,
    employee_number,
    pivot_column_value,
    item_abbreviation,

from
    {{ ref("stg_surveys__staff_info_archive") }} unpivot (
        pivot_column_value for item_abbreviation in (
            respondent_name,
            gender_identity,
            level_of_education,
            undergraduate_school,
            years_exp_outside_kipp,
            years_teaching_in_njfl,
            years_teaching_outside_njfl,
            alumni_status,
            community_grew_up,
            community_professional_exp,
            languages_spoken,
            path_to_education,
            race_ethnicity,
            relay_status
        )
    )
