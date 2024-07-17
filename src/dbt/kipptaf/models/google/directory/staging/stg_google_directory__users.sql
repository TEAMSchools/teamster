select
    id,
    primaryemail as primary_email,
    orgunitpath as org_unit_path,
    recoveryemail as recovery_email,
    recoveryphone as recovery_phone,
    suspensionreason as suspension_reason,
    lastlogintime as last_login_time,
    creationtime as creation_time,
    isadmin as is_admin,
    isdelegatedadmin as is_delegated_admin,
    isenforcedin2sv as is_enforced_in_2sv,
    isenrolledin2sv as is_enrolled_in_2sv,
    ismailboxsetup as is_mailbox_setup,
    agreedtoterms as agreed_to_terms,
    archived,
    suspended,
    changepasswordatnextlogin as change_password_at_next_login,
    includeinglobaladdresslist as include_in_global_address_list,
    ipwhitelisted as ip_whitelisted,
    thumbnailphotoetag as thumbnail_photo_etag,
    thumbnailphotourl as thumbnail_photo_url,
    customerid as customer_id,
    etag,
    kind,

    /* records */
    gender.type as gender__type,
    name.familyname as name__family_name,
    name.fullname as name__full_name,
    name.givenname as name__given_name,
    notes.value as notes__value,
    customschemas.student_attributes.student_number
    as custom_schemas__student_attributes__student_number,

    /* repeated */
    aliases,
    noneditablealiases as non_editable_aliases,

    /* repeated records */
    emails,
    externalids as external_ids,
    languages,
    organizations,
    phones,
    relations,
from {{ source("google_directory", "src_google_directory__users") }}
