select
    id,
    `name`,
    createdbyid as created_by_id,
    createddate as created_date,
    lastactivitydate as last_activity_date,
    lastmodifiedbyid as last_modified_by_id,
    lastmodifieddate as last_modified_date,
    lastreferenceddate as last_referenced_date,
    lastvieweddate as last_viewed_date,
    ownerid as owner_id,
    systemmodstamp as system_modstamp,
    applicable_grade_level__c as applicable_grade_level,
    applicable_school_year__c as applicable_school_year,
    efc_from_fafsa_for_this_year__c as efc_from_fafsa_for_this_year,
    enrollment__c as enrollment,
    federal_work_study__c as federal_work_study,
    institutional_grant__c as institutional_grant,
    institutional_scholarship__c as institutional_scholarship,
    institutional_work_study__c as institutional_work_study,
    offer_date__c as offer_date,
    other_private_loan__c as other_private_loan,
    parent_plus_loan__c as parent_plus_loan,
    pell_grant__c as pell_grant,
    perkins_loan__c as perkins_loan,
    seog__c as seog,
    stafford_loan_subsidized__c as stafford_loan_subsidized,
    stafford_loan_unsubsidized__c as stafford_loan_unsubsidized,
    state_grant__c as state_grant,
    status__c as status,
    subsequent_financial_aid_award_count__c as subsequent_financial_aid_award_count,
    tap__c as tap,
    total_aid_available__c as total_aid_available,
    total_cost_of_attendance__c as total_cost_of_attendance,
    unmet_need__c as unmet_need,
from {{ source("kippadb", "subsequent_financial_aid_award") }}
where not isdeleted
