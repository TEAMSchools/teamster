with
    roster as (
        -- trunk-ignore(sqlfluff/ST06): contract column order is mandated
        select
            sr.formatted_name as respondent,
            sr.google_email,

            lc.location_clean_name,
            lc.campus_name,

            case
                sr.home_business_unit_name
                when 'TEAM'
                then 'TEAM Academy Charter School'
                when 'KCNA'
                then 'KIPP Cooper Norcross Academy'
                when 'MIA'
                then 'KIPP Miami'
                when 'KNJ'
                then 'KIPP TEAM and Family Schools Inc.'
                else sr.home_business_unit_name
            end as home_business_unit_name,
            sr.home_department_name,
            sr.job_function,
            sr.job_title,

            sr.mail,
            sr.user_principal_name,
            sr.sam_account_name,

            sr.reports_to_mail,
            sr.reports_to_sam_account_name,
        from {{ ref("int_people__staff_roster") }} as sr
        left join
            {{ ref("int_people__location_crosswalk") }} as lc
            on sr.home_work_location_name = lc.location_name
    ),

    form_responses as (
        select
            form_id,
            info_document_title as survey_title,
            item_id,
            item_title as section_title,
            question_id,
            question_title,
            item_abbreviation,
            response_id,
            last_submitted_date_local,
            respondent_email,
            text_value,

            if(
                regexp_contains(text_value, r'^-?\d+$'),
                safe_cast(text_value as int),
                null
            ) as text_value_int,
        from {{ ref("int_google_forms__form_responses") }}
        -- filtering for Operations EKG Form
        where
            form_id = '1J4ce4NUNVZq5ia7HCPUfhuiWjqILik2mBu-FVaRwxFM'
            and text_value is not null
    ),

    responses_pivoted as (
        select
            *,

            -- pivoting out walkthrough round and school selection items 
            max(
                case
                    when form_responses.item_id = '27596233'
                    then form_responses.text_value
                end
            ) over (partition by form_responses.response_id) as walkthrough_round,

            max(
                case
                    when form_responses.item_id = '669334db'
                    then form_responses.text_value
                end
            ) over (partition by form_responses.response_id) as school,
        from form_responses
    ),

    final as (
        select
            roster.*,
            responses_pivoted.*,

            sc.location_grade_band as grade_band,
            -- the walked school, resolved to its canonical name. distinct from
            -- roster.location_clean_name, which is the respondent's own location
            sc.location_clean_name as school_clean_name,
        from responses_pivoted
        left join
            roster
            on (
                lower(regexp_extract(responses_pivoted.respondent_email, r'^([^@]+)'))
                = roster.sam_account_name
                or responses_pivoted.respondent_email = roster.google_email
            )
        left join
            {{ ref("int_people__location_crosswalk") }} as sc
            on responses_pivoted.school = sc.location_name
        where responses_pivoted.item_id not in ('27596233', '669334db')
    )

select *,
from final
