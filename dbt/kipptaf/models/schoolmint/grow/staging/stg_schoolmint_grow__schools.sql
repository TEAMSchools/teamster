select
    _id as school_id,
    `name`,
    abbreviation,
    `address`,
    archivedat as archived_at,
    city,
    created,
    district,
    gradespan as grade_span,
    highgrade as high_grade,
    internalid as internal_id,
    lastmodified as last_modified,
    lowgrade as low_grade,
    phone,
    principal,
    region,
    `state`,
    zip,

    /* repeated records */
    admins,
    assistantadmins as assistant_admins,
    noninstructionaladmins as non_instructional_admins,
    observationgroups as observation_groups,
from {{ source("schoolmint_grow", "src_schoolmint_grow__schools") }}
where _dagster_partition_key = 'f'
