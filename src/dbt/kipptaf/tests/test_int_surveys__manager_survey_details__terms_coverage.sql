select ms.campaign_academic_year, ms.campaign_reporting_term, count(*) as orphan_rows,
from {{ ref("int_surveys__manager_survey_details") }} as ms
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on rt.`name` = 'Manager Survey'
    and ms.campaign_academic_year = rt.academic_year
    and ms.campaign_reporting_term = rt.code
    and rt.type = 'SURVEY'
where ms.campaign_academic_year is not null and rt.academic_year is null
group by 1, 2
