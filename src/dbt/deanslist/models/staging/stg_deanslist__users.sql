with
    users as (
        select
            cast(nullif(accountid, '') as int) as account_id,
            cast(nullif(dlschoolid, '') as int) as dl_school_id,
            cast(nullif(userstateid, '') as int) as user_state_id,

            nullif(dluserid, '') as dl_user_id,
            nullif(userschoolid, '') as user_school_id,
            nullif(active, '') as active,
            nullif(email, '') as email,
            nullif(firstname, '') as first_name,
            nullif(groupname, '') as group_name,
            nullif(lastname, '') as last_name,
            nullif(middlename, '') as middle_name,
            nullif(schoolname, '') as school_name,
            nullif(staffrole, '') as staff_role,
            nullif(title, '') as title,
            nullif(username, '') as username,
        from {{ source("deanslist", "src_deanslist__users") }}
    )

select
    * except (active),

    concat(first_name, ' ', last_name) as full_name,
    concat(last_name, ', ', first_name) as lastfirst,

    if(active = 'Y', true, false) as active,
from users
