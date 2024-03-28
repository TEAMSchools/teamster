with
    gpa_clean as (
        select
            src.id as `id`,
            src.`name` as `name`,
            src.createdbyid as `created_by_id`,
            src.createddate as `created_date`,
            src.lastmodifiedbyid as `last_modified_by_id`,
            src.lastmodifieddate as `last_modified_date`,
            src.recordtypeid as `record_type_id`,
            src.systemmodstamp as `system_modstamp`,
            src.academic_status__c as `academic_status`,
            src.college_standing__c as `college_standing`,
            src.college_term__c as `college_term`,
            src.credits__c as `credits`,
            src.credits_in_major__c as `credits_in_major`,
            src.credits_required_for_graduation__c as `credits_required_for_graduation`,
            src.cumulative_credits_attempted__c as `cumulative_credits_attempted`,
            src.cumulative_credits_earned__c as `cumulative_credits_earned`,
            src.enrollment__c as `enrollment`,
            src.gpa__c as `gpa`,
            src.gpa_count__c as `gpa_count`,
            src.gpa_in_major__c as `gpa_in_major`,
            src.major__c as `major`,
            src.major_area__c as `major_area`,
            src.major_cumulative_credits_attempted__c
            as `major_cumulative_credits_attempted`,
            src.major_cumulative_credits_earned__c as `major_cumulative_credits_earned`,
            src.major_cumulative_gpa__c as `major_cumulative_gpa`,
            src.major_declared__c as `major_declared`,
            src.major_semester_credits_attempted__c
            as `major_semester_credits_attempted`,
            src.major_semester_credits_earned__c as `major_semester_credits_earned`,
            src.major_semester_gpa__c as `major_semester_gpa`,
            src.scale__c as `scale`,
            src.semester_credits_attempted__c as `semester_credits_attempted`,
            src.semester_credits_earned__c as `semester_credits_earned`,
            src.semester_gpa__c as `semester_gpa`,
            src.source__c as `source`,
            src.student__c as `student`,
            src.term__c as `term`,
            src.term_number__c as `term_number`,
            src.term_type__c as `term_type`,
            src.time_period__c as `time_period`,
            src.time_period_sort_order__c as `time_period_sort_order`,
            src.transcript_date__c as `transcript_date`,
            src.type__c as `type`,
        from {{ source("kippadb", "gpa") }} as src
        where not isdeleted
    )

select
    *,
    case
        when extract(month from transcript_date) in (1, 12)
        then 'Fall'
        when extract(month from transcript_date) = 5
        then 'Spring'
    end as semester,
    {{
        teamster_utils.date_to_fiscal_year(
            date_field="transcript_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from gpa_clean
