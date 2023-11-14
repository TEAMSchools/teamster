with response_identifiers as (
    select fr.form_id as survey_id,
       fr.info_title as survey_title,
       fr.response_id as survey_response_id,
       
       rt.Academic_year as campaign_academic_year,
       rt.name as campaign_name,
       rt.code as campaign_reporting_term,

       TIMESTAMP(fr.create_time) as date_started,
       TIMESTAMP(fr.last_submitted_time) as date_submitted,

       safe_cast(regexp_extract(fr.text_value, r'\((\d{6})\)') as integer) as respondent_df_employee_number,
       fr.respondent_email
       
from {{ ref("base_google_forms__form_responses") }} as fr
left join {{ ref("stg_reporting__terms") }} as rt
    on DATE(fr.last_submitted_time) between rt.Start_Date and rt.End_Date
   AND rt.type = 'SURVEY'
   AND rt.code IN ('SUP1','SUP2') 
WHERE fr.question_item__question__question_id = '55f7fb30'
  AND fr.form_id = '1YdgXFZE1yjJa-VfpclZrBtxvW0w4QvxNrvbDUBxIiWI'  

UNION DISTINCT

    select fr.form_id as survey_id,
       fr.info_title as survey_title,
       fr.response_id as survey_response_id,
       
       rt.Academic_year as campaign_academic_year,
       rt.name as campaign_name,
       rt.code as campaign_reporting_term,

       TIMESTAMP(fr.create_time) as date_started,
       TIMESTAMP(fr.last_submitted_time) as date_submitted,

       up.employee_number as respondent_df_employee_number,
       fr.respondent_email
       
from {{ ref("base_google_forms__form_responses") }} as fr
left join {{ ref("stg_reporting__terms") }} as rt
    on DATE(fr.last_submitted_time) between rt.Start_Date and rt.End_Date
   AND rt.type = 'SURVEY'
   AND rt.code IN ('SUP1','SUP2')
inner join {{ ref("stg_ldap__user_person") }} as up 
   on fr.respondent_email = up.google_email
WHERE fr.question_item__question__question_id = '55f7fb30'
  AND fr.form_id = '1YdgXFZE1yjJa-VfpclZrBtxvW0w4QvxNrvbDUBxIiWI'  
    )

select ri.survey_id,
       ri.survey_title,
       ri.survey_response_id,
       ri.date_started,
       ri.date_submitted,
       ri.campaign_academic_year,
       ri.campaign_name,
       ri.campaign_reporting_term,
       CASE WHEN safe_cast(fr.text_value as integer) is null then 1 else 0 end as is_open_ended,

       fi.abbreviation as question_shortname,
       fi.title as question_title,

       fr.text_value as answer,
       safe_cast(fr.text_value as integer) as answer_value,

       ri.respondent_df_employee_number,
       eh.preferred_name_lastfirst,
       ri.respondent_email,

       --fill out with remaining fields from:
       --https://github.com/TEAMSchools/mssql-warehouse/blob/f32a07eedc29a622e90b1175ff3b5848a01eb91b/gabby/surveys/view/cmo_engagement_regional_survey_detail.sql#L2

from response_identifiers as ri
inner join {{ ref("base_google_forms__form_responses") }} as fr
  on ri.survey_id = fr.form_id
 and ri.survey_response_id = fr.response_id
inner join {{ source("google_forms","src_google_forms__form_items_extension") }} as fi
  on fr.form_id = fi.form_id
 and fr.question_item__question__question_id = fi.question_id
inner join {{ ref("base_people__staff_roster_history") }} as eh
  on ri.respondent_df_employee_number = eh.employee_number
 and ri.date_submitted between eh.work_assignment__fivetran_start and eh.work_assignment__fivetran_end

 --ADD HISTORIC DATE WITH UNION