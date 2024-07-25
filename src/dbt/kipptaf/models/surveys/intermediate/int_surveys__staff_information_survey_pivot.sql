with
    form_responses as (
        select
            response_id,
            respondent_email,
            item_abbreviation,
            safe_cast(last_submitted_time as timestamp) as last_submitted_time,
            coalesce(text_value, file_upload_file_id) as pivot_column_value,

        from {{ ref("base_google_forms__form_responses") }}
        where form_id = '1jpeMof_oQ9NzTw85VFsA5A7G9VrH3XkSc_nZDFz07nA'
    ),

    agg_multis as (
        select
            response_id,
            respondent_email,
            last_submitted_time,
            item_abbreviation,
            string_agg(pivot_column_value) as pivot_column_value,
        from form_responses
        group by response_id, respondent_email, last_submitted_time, item_abbreviation
    ),

    response_union as (
        select
            response_id,
            respondent_email,
            last_submitted_time,
            item_abbreviation,
            pivot_column_value,
        from agg_multis

        union all

        select
            null as response_id,
            respondent_email,
            last_submitted_time,
            pivot_column_value,
            item_abbreviation,
        from {{ ref("int_surveys__staff_info_archive_unpivot") }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="response_union",
                partition_by="respondent_email, item_abbreviation",
                order_by="last_submitted_time desc",
            )
        }}
    )
select
    response_id,
    respondent_email,
    last_submitted_time,

    /* pivot cols */
    additional_languages,
    cert_barriers,
    cert_out_of_state_details,
    cert_status,
    cert_steps_taken,
    fl_cert_endorsement_1,
    fl_cert_endorsement_2,
    fl_cert_endorsement_3,
    fl_cert_endorsement_4,
    fl_cert_endorsement_5,
    fl_open_to_student_teacher,
    gender_identity,
    languages_spoken,
    level_of_education,
    nj_cert_document_link_1,
    nj_cert_document_link_2,
    nj_cert_document_link_3,
    nj_cert_document_link_4,
    nj_cert_document_link_5,
    nj_cert_endorsement_1,
    nj_cert_endorsement_2,
    nj_cert_endorsement_3,
    nj_cert_endorsement_4,
    nj_cert_endorsement_5,
    nj_cert_type_1,
    nj_cert_type_2,
    nj_cert_type_3,
    nj_cert_type_4,
    nj_cert_type_5,
    race_ethnicity,
    respondent_name,
    undergraduate_school,
    updates_open_ended,
    praxis_document_link,
    safe_cast(years_teaching_in_njfl as numeric) as years_teaching_in_njfl,
    safe_cast(years_exp_outside_kipp as numeric) as years_exp_outside_kipp,
    safe_cast(years_teaching_outside_njfl as numeric) as years_teaching_outside_njfl,
    safe_cast(regexp_extract(respondent_name, r'(\d{6})') as int) as employee_number,
    replace(alumni_status, ',', '.') as alumni_status,
    replace(path_to_education, ',', '.') as path_to_education,
    replace(relay_status, ',', '.') as relay_status,
    replace(
        community_grew_up, 'Newark, Camden, and/or Miami', 'the cities we serve'
    ) as community_grew_up,
    replace(
        community_professional_exp,
        'Newark, Camden, and/or Miami',
        'the cities we serve'
    ) as community_professional_exp,
    safe_cast(fl_cert_expiration_1 as date) as fl_cert_expiration_1,
    safe_cast(fl_cert_expiration_2 as date) as fl_cert_expiration_2,
    safe_cast(fl_cert_expiration_3 as date) as fl_cert_expiration_3,
    safe_cast(fl_cert_expiration_4 as date) as fl_cert_expiration_4,
    safe_cast(fl_cert_expiration_5 as date) as fl_cert_expiration_5,
    safe_cast(nj_cert_issue_date_1 as date) as nj_cert_issue_date_1,
    safe_cast(nj_cert_issue_date_2 as date) as nj_cert_issue_date_2,
    safe_cast(nj_cert_issue_date_3 as date) as nj_cert_issue_date_3,
    safe_cast(nj_cert_issue_date_4 as date) as nj_cert_issue_date_4,
    safe_cast(nj_cert_issue_date_5 as date) as nj_cert_issue_date_5,
    if(cert_required = 'Yes', true, false) as cert_required,
    if(fl_additional_cert_1 = 'Yes', true, false) as fl_additional_cert_1,
    if(nj_cert_additional_1 = 'Yes', true, false) as nj_cert_additional_1,
    case
        when regexp_contains(race_ethnicity, 'I decline to state')
        then 'Decline to State'
        when race_ethnicity = 'Latinx/Hispanic/Chicana(o)'
        then 'Latinx/Hispanic/Chicana(o)'
        when race_ethnicity = 'My racial/ethnic identity is not listed'
        then 'Race/Ethnicity Not Listed'
        when regexp_contains(race_ethnicity, 'Bi/Multiracial')
        then 'Bi/Multiracial'
        when regexp_contains(race_ethnicity, ',')
        then 'Bi/Multiracial'
        else race_ethnicity
    end as race_ethnicity_reporting,
    -- row_number() over (
    --     partition by employee_number order by last_submitted_time desc
    -- ) as rn_submission,
from
    deduplicate pivot (
        max(pivot_column_value) for item_abbreviation in (
            'additional_languages',
            'alumni_status',
            'cert_barriers',
            'cert_out_of_state_details',
            'cert_required',
            'cert_status',
            'cert_steps_taken',
            'community_grew_up',
            'community_professional_exp',
            'fl_additional_cert_1',
            'fl_cert_endorsement_1',
            'fl_cert_endorsement_2',
            'fl_cert_endorsement_3',
            'fl_cert_endorsement_4',
            'fl_cert_endorsement_5',
            'fl_cert_expiration_1',
            'fl_cert_expiration_2',
            'fl_cert_expiration_3',
            'fl_cert_expiration_4',
            'fl_cert_expiration_5',
            'fl_open_to_student_teacher',
            'gender_identity',
            'languages_spoken',
            'level_of_education',
            'nj_cert_additional_1',
            'nj_cert_document_link_1',
            'nj_cert_document_link_2',
            'nj_cert_document_link_3',
            'nj_cert_document_link_4',
            'nj_cert_document_link_5',
            'nj_cert_endorsement_1',
            'nj_cert_endorsement_2',
            'nj_cert_endorsement_3',
            'nj_cert_endorsement_4',
            'nj_cert_endorsement_5',
            'nj_cert_issue_date_1',
            'nj_cert_issue_date_2',
            'nj_cert_issue_date_3',
            'nj_cert_issue_date_4',
            'nj_cert_issue_date_5',
            'nj_cert_type_1',
            'nj_cert_type_2',
            'nj_cert_type_3',
            'nj_cert_type_4',
            'nj_cert_type_5',
            'path_to_education',
            'race_ethnicity',
            'relay_status',
            'respondent_name',
            'undergraduate_school',
            'years_exp_outside_kipp',
            'years_teaching_in_njfl',
            'years_teaching_outside_njfl',
            'updates_open_ended',
            'praxis_document_link'
        )
    )
