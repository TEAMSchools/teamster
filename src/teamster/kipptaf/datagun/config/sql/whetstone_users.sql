select distinct
    user_internal_id,
    group_type,
    group_name,
    [user_id],
    archived_at,
    user_email,
    user_email_ws,
    [user_name],
    user_name_ws,
    inactive,
    inactive_ws,
    coach_id,
    coach_id_ws,
    school_id,
    school_id_ws,
    grade_id,
    grade_id_ws,
    course_id,
    course_id_ws,
    role_id,
    role_id_ws,
    role_names
from extracts.whetstone_users
where
    not (concat(inactive, inactive_ws) = '11' and archived_at is not null)
    and (
        /* create user */
        [user_id] is null
        /* update user */
        or isnull (inactive, '') != isnull (inactive_ws, '')
        or isnull (coach_id, '') != isnull (coach_id_ws, '')
        or isnull (school_id, '') != isnull (school_id_ws, '')
        or isnull (grade_id, '') != isnull (grade_id_ws, '')
        or isnull (course_id, '') != isnull (course_id_ws, '')
        or isnull (role_id, '') != isnull (role_id_ws, '')
        or isnull (user_email, '') != isnull (user_email_ws, '')
        or isnull ([user_name], '') != isnull (user_name_ws, '')
        or isnull (group_type, '') != isnull (group_type_ws, '')
    )
