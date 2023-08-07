select
    roleassignmentid as `role_assignment_id`,
    roleid as `role_id`,
    kind as `kind`,
    etag as `etag`,
    assignedto as `assigned_to`,
    assigneetype as `assignee_type`,
    scopetype as `scope_type`,
    orgunitid as `org_unit_id`,
    condition as `condition`,
from {{ source("google_directory", "src_google_directory__role_assignments") }}
