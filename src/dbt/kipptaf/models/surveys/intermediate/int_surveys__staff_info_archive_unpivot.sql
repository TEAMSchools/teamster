select
    respondent_email,
    employee_number,
    last_submitted_timestamp,
    pivot_column_value,
    item_abbreviation,
from
    {{ ref("stg_surveys__staff_info_archive") }} unpivot (
        pivot_column_value for item_abbreviation in (
            alumni_status,
            community_grew_up,
            community_professional_exp,
            gender_identity,
            languages_spoken,
            level_of_education,
            path_to_education,
            race_ethnicity,
            relay_status,
            undergraduate_school,
            years_exp_outside_kipp,
            years_teaching_in_njfl,
            years_teaching_outside_njfl
        )
    )
