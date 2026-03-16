with
    enr_clean as (
        select
            e.id,
            e.`name`,
            e.recordtypeid as record_type_id,
            e.createdbyid as created_by_id,
            e.createddate as created_date,
            e.lastactivitydate as last_activity_date,
            e.lastmodifiedbyid as last_modified_by_id,
            e.lastmodifieddate as last_modified_date,
            e.lastreferenceddate as last_referenced_date,
            e.lastvieweddate as last_viewed_date,
            e.systemmodstamp as system_modstamp,

            e.account_type__c as account_type,
            e.actual_end_date__c as actual_end_date,
            e.anticipated_graduation__c as anticipated_graduation,
            e.apex_updated__c as apex_updated,
            e.attending_status__c as attending_status,
            e.class_rank_percentile__c as class_rank_percentile,
            e.college_major_declared__c as college_major_declared,
            e.college_standing__c as college_standing,
            e.college_transcript_sort_order__c as college_transcript_sort_order,
            e.created_for_nsc_data__c as created_for_nsc_data,
            e.credential_attainment_sort_order__c as credential_attainment_sort_order,
            e.date_last_verified__c as date_last_verified,
            e.diploma_or_degree_level__c as diploma_or_degree_level,
            e.do_not_overwrite_with_nsc_data__c as do_not_overwrite_with_nsc_data,
            e.do_not_send_kipp_hs_class_email__c as do_not_send_kipp_hs_class_email,
            e.dual_enrollment__c as dual_enrollment,
            e.endinggrade__c as ending_grade,
            e.enrollment_count__c as enrollment_count,
            e.final_gpa__c as final_gpa,
            e.grad_year__c as grad_year,
            e.has_terminal_status__c as has_terminal_status,
            e.highest_sat_score__c as highest_sat_score,
            e.living_on_campus__c as living_on_campus,
            e.major__c as major,
            e.major_area__c as major_area,
            e.major_status__c as major_status,
            e.matriculated_terms__c as matriculated_terms,
            e.most_recent_term_start_date__c as most_recent_term_start_date,
            e.notes__c as notes,
            e.nsc_match_code__c as nsc_match_code,
            e.nsc_verified__c as nsc_verified,
            e.number_of_marking_periods__c as number_of_marking_periods,
            e.of_credits_required_for_graduation__c
            as of_credits_required_for_graduation,
            e.other_major__c as other_major,
            e.prod_migration__c as prod_migration,
            e.pursuing_degree_type__c as pursuing_degree_type,
            e.school__c as school,
            e.source__c as `source`,
            e.special_enrollment_circumstance__c as special_enrollment_circumstance,
            e.start_date__c as `start_date`,
            e.startinggrade__c as starting_grade,
            e.status__c as `status`,
            e.student__c as student,
            e.student_hs_cohort__c as student_hs_cohort,
            e.subtype__c as subtype,
            e.terminal_status_sort_order__c as terminal_status_sort_order,
            e.terms__c as terms,
            e.transfer_reason__c as transfer_reason,
            e.type__c as `type`,

            n.overgrad_urm_grad_rate as og_urm,
        from {{ source("kippadb", "enrollment") }} as e
        left join
            {{ ref("stg_google_sheets__kippadb__nsc_crosswalk") }} as n
            on e.id = n.account_id
            and n.rn_account = 1
        where not e.isdeleted
    )

select
    ec.*,

    extract(year from ec.`start_date`) as start_date_year,

    row_number() over (
        partition by ec.student, ec.school, extract(year from ec.`start_date`)
        order by ec.`start_date` asc
    ) as rn_stu_school_start,
from enr_clean as ec
