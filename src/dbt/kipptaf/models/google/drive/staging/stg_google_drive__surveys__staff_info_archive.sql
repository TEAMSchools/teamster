select
    * except (
        `timestamp`,
        community_professional_experience,
        years_exp_outside_kipp,
        years_teaching_in_njfl,
        years_teaching_outside_njfl
    ),

    `timestamp` as last_submitted_timestamp,

    /* multiselect_options */
    community_professional_experience as community_professional_exp,

    cast(years_exp_outside_kipp as string) as years_exp_outside_kipp,
    cast(years_teaching_in_njfl as string) as years_teaching_in_njfl,
    cast(years_teaching_outside_njfl as string) as years_teaching_outside_njfl,

    cast(regexp_extract(respondent_name, r'(\d{6})') as int) as employee_number,
from {{ source("surveys", "src_surveys__staff_info_archive") }}
