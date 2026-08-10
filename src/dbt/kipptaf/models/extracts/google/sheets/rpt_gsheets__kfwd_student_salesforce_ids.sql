select
    lastfirst as student_name,
    last_name,
    first_name,
    contact_birthdate as birthdate,
    ktc_cohort as cohort,
    region,
    contact_id as salesforce_contact_id,
    student_number,
    record_type_name as record_type,
    ktc_status,
from {{ ref("int_kippadb__roster") }}
/* MS8 is excluded rather than enumerating the statuses to keep (as
   rpt_tableau__kfwd_dashboard does) so any newly introduced ktc_status appears
   here by default: a student missing from the lookup causes the mis-attribution
   this feed exists to prevent, while an extra middle schooler is inert. */
where contact_id is not null and ktc_status != 'MS8'
