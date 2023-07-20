with
    gpa_clean as (
        select
            id as `id`,
            `name` as `name`,
            createdbyid as `created_by_id`,
            createddate as `created_date`,
            lastmodifiedbyid as `last_modified_by_id`,
            lastmodifieddate as `last_modified_date`,
            recordtypeid as `record_type_id`,
            systemmodstamp as `system_modstamp`,
            academic_status__c as `academic_status`,
            college_standing__c as `college_standing`,
            college_term__c as `college_term`,
            credits__c as `credits`,
            credits_in_major__c as `credits_in_major`,
            credits_required_for_graduation__c as `credits_required_for_graduation`,
            cumulative_credits_attempted__c as `cumulative_credits_attempted`,
            cumulative_credits_earned__c as `cumulative_credits_earned`,
            enrollment__c as `enrollment`,
            gpa__c as `gpa`,
            gpa_count__c as `gpa_count`,
            gpa_in_major__c as `gpa_in_major`,
            major__c as `major`,
            major_area__c as `major_area`,
            major_cumulative_credits_attempted__c
            as `major_cumulative_credits_attempted`,
            major_cumulative_credits_earned__c as `major_cumulative_credits_earned`,
            major_cumulative_gpa__c as `major_cumulative_gpa`,
            major_declared__c as `major_declared`,
            major_semester_credits_attempted__c as `major_semester_credits_attempted`,
            major_semester_credits_earned__c as `major_semester_credits_earned`,
            major_semester_gpa__c as `major_semester_gpa`,
            scale__c as `scale`,
            semester_credits_attempted__c as `semester_credits_attempted`,
            semester_credits_earned__c as `semester_credits_earned`,
            semester_gpa__c as `semester_gpa`,
            source__c as `source`,
            student__c as `student`,
            term__c as `term`,
            term_number__c as `term_number`,
            term_type__c as `term_type`,
            time_period__c as `time_period`,
            time_period_sort_order__c as `time_period_sort_order`,
            transcript_date__c as `transcript_date`,
            type__c as `type`,
        from {{ source("kippadb", "gpa") }}
        where not isdeleted
    )

select
    *,
    case month(transcript_date) when 1 then 'fall' when 5 then 'spr' end as semester,
    {{
        teamster_utils.date_to_fiscal_year(
            date_field="transcript_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from gpa_clean
