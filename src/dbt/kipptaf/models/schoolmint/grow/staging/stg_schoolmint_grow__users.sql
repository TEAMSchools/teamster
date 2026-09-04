select
    _id as user_id,
    internalid as internal_id,
    archivedat as archived_at,
    email,
    `name`,
    coach,
    readonly as read_only,
    inactive,

    /* records */
    defaultinformation.course as default_information_course,
    defaultinformation.gradelevel as default_information_grade_level,
    defaultinformation.school as default_information_school,

    /* repeated records */
    roles,
    regionaladminschools as regional_admin_schools,

    /* transformations */
    safe_cast(internalid as int) as internal_id_int,
from {{ source("schoolmint_grow", "src_schoolmint_grow__users") }}
where coalesce(safe_cast(internalid as int), 0) != 999999
