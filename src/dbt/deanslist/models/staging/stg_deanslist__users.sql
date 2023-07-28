select
    safe_cast(nullif(dluserid, '') as int) as `dl_user_id`,

    safe_cast(nullif(accountid, '') as int) as `account_id`,
    safe_cast(nullif(dlschoolid, '') as int) as `dl_school_id`,
    safe_cast(nullif(userschoolid, '') as int) as `user_school_id`,
    safe_cast(nullif(userstateid, '') as int) as `user_state_id`,

    nullif(username, '') as `username`,
    nullif(email, '') as `email`,
    nullif(staffrole, '') as `staff_role`,
    nullif(groupname, '') as `group_name`,
    nullif(schoolname, '') as `school_name`,
    nullif(title, '') as `title`,
    nullif(firstname, '') as `first_name`,
    nullif(middlename, '') as `middle_name`,
    nullif(lastname, '') as `last_name`,

    if(active = 'Y', true, false) as `active`,
from {{ source("deanslist", "src_deanslist__users") }}
