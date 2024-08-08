with
    gpa_clean as (
        select
            source_gpa.id,
            source_gpa.name,
            source_gpa.createdbyid as created_by_id,
            source_gpa.createddate as created_date,
            source_gpa.lastmodifiedbyid as last_modified_by_id,
            source_gpa.lastmodifieddate as last_modified_date,
            source_gpa.recordtypeid as record_type_id,
            source_gpa.systemmodstamp as system_modstamp,
            source_gpa.academic_status__c as academic_status,
            source_gpa.college_standing__c as college_standing,
            source_gpa.college_term__c as college_term,
            source_gpa.credits__c as credits,
            source_gpa.credits_in_major__c as credits_in_major,
            source_gpa.credits_required_for_graduation__c
            as credits_required_for_graduation,
            source_gpa.cumulative_credits_attempted__c as cumulative_credits_attempted,
            source_gpa.cumulative_credits_earned__c as cumulative_credits_earned,
            source_gpa.enrollment__c as enrollment,
            source_gpa.gpa__c as gpa,
            source_gpa.gpa_count__c as gpa_count,
            source_gpa.gpa_in_major__c as gpa_in_major,
            source_gpa.major__c as major,
            source_gpa.major_area__c as major_area,
            source_gpa.major_cumulative_credits_attempted__c
            as major_cumulative_credits_attempted,
            source_gpa.major_cumulative_credits_earned__c
            as major_cumulative_credits_earned,
            source_gpa.major_cumulative_gpa__c as major_cumulative_gpa,
            source_gpa.major_declared__c as major_declared,
            source_gpa.major_semester_credits_attempted__c
            as major_semester_credits_attempted,
            source_gpa.major_semester_credits_earned__c
            as major_semester_credits_earned,
            source_gpa.major_semester_gpa__c as major_semester_gpa,
            source_gpa.scale__c as scale,
            source_gpa.semester_credits_attempted__c as semester_credits_attempted,
            source_gpa.semester_credits_earned__c as semester_credits_earned,
            source_gpa.semester_gpa__c as semester_gpa,
            source_gpa.source__c as `source`,
            source_gpa.student__c as student,
            source_gpa.term__c as term,
            source_gpa.term_number__c as term_number,
            source_gpa.term_type__c as term_type,
            source_gpa.time_period__c as time_period,
            source_gpa.time_period_sort_order__c as time_period_sort_order,
            source_gpa.transcript_date__c as transcript_date,
            source_gpa.type__c as `type`,
        from {{ source("kippadb", "gpa") }} as source_gpa
        where not source_gpa.isdeleted
    )

select
    *,

    case
        when extract(month from transcript_date) in (1, 12)
        then 'Fall'
        when extract(month from transcript_date) in (5, 6)
        then 'Spring'
    end as semester,

    {{
        teamster_utils.date_to_fiscal_year(
            date_field="transcript_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from gpa_clean
