with
    enr_clean as (
        select
            id,
            `name`,
            recordtypeid as record_type_id,
            createdbyid as created_by_id,
            createddate as created_date,
            lastactivitydate as last_activity_date,
            lastmodifiedbyid as last_modified_by_id,
            lastmodifieddate as last_modified_date,
            lastreferenceddate as last_referenced_date,
            lastvieweddate as last_viewed_date,
            systemmodstamp as system_modstamp,

            account_type__c as account_type,
            actual_end_date__c as actual_end_date,
            anticipated_graduation__c as anticipated_graduation,
            apex_updated__c as apex_updated,
            attending_status__c as attending_status,
            class_rank_percentile__c as class_rank_percentile,
            college_major_declared__c as college_major_declared,
            college_standing__c as college_standing,
            college_transcript_sort_order__c as college_transcript_sort_order,
            created_for_nsc_data__c as created_for_nsc_data,
            credential_attainment_sort_order__c as credential_attainment_sort_order,
            date_last_verified__c as date_last_verified,
            diploma_or_degree_level__c as diploma_or_degree_level,
            do_not_overwrite_with_nsc_data__c as do_not_overwrite_with_nsc_data,
            do_not_send_kipp_hs_class_email__c as do_not_send_kipp_hs_class_email,
            dual_enrollment__c as dual_enrollment,
            endinggrade__c as ending_grade,
            enrollment_count__c as enrollment_count,
            final_gpa__c as final_gpa,
            grad_year__c as grad_year,
            has_terminal_status__c as has_terminal_status,
            highest_sat_score__c as highest_sat_score,
            living_on_campus__c as living_on_campus,
            major__c as major,
            major_area__c as major_area,
            major_status__c as major_status,
            matriculated_terms__c as matriculated_terms,
            most_recent_term_start_date__c as most_recent_term_start_date,
            notes__c as notes,
            nsc_match_code__c as nsc_match_code,
            nsc_verified__c as nsc_verified,
            number_of_marking_periods__c as number_of_marking_periods,
            of_credits_required_for_graduation__c as of_credits_required_for_graduation,
            other_major__c as other_major,
            prod_migration__c as prod_migration,
            pursuing_degree_type__c as pursuing_degree_type,
            school__c as school,
            source__c as `source`,
            special_enrollment_circumstance__c as special_enrollment_circumstance,
            start_date__c as `start_date`,
            startinggrade__c as starting_grade,
            status__c as `status`,
            student__c as student,
            student_hs_cohort__c as student_hs_cohort,
            subtype__c as subtype,
            terminal_status_sort_order__c as terminal_status_sort_order,
            terms__c as terms,
            transfer_reason__c as transfer_reason,
            type__c as `type`,
        from {{ source("kippadb", "enrollment") }}
        where not isdeleted
    )

select
    *,

    extract(year from `start_date`) as start_date_year,

    row_number() over (
        partition by student, school, extract(year from `start_date`)
        order by `start_date` asc
    ) as rn_stu_school_start,
from enr_clean
