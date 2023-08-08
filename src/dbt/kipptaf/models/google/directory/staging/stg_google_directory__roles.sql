select
    roleid as `role_id`,
    rolename as `role_name`,
    roledescription as `role_description`,
    issystemrole as `is_system_role`,
    issuperadminrole as `is_super_admin_role`,
    kind as `kind`,
    etag as `etag`,
    roleprivileges as `role_privileges`,
from {{ source("google_directory", "src_google_directory__roles") }}
