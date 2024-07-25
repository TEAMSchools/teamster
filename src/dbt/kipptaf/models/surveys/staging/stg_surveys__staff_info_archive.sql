select
    respondent_email,
    `timestamp` as last_submitted_timestamp,
    respondent_name,
    gender_identity,
    level_of_education,
    undergraduate_school,

    /* multiselect_options */
    alumni_status,
    community_grew_up,
    community_professional_experience as community_professional_exp,
    languages_spoken,
    path_to_education,
    race_ethnicity,
    relay_status,

    cast(years_exp_outside_kipp as string) as years_exp_outside_kipp,
    cast(years_teaching_in_njfl as string) as years_teaching_in_njfl,
    cast(years_teaching_outside_njfl as string) as years_teaching_outside_njfl,

    cast(regexp_extract(respondent_name, r'(\d{6})') as int) as employee_number,
from {{ source("surveys", "src_surveys__staff_info_archive") }}
