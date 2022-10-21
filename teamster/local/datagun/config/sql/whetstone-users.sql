SELECT DISTINCT
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
FROM
    gabby.extracts.whetstone_users
WHERE
    NOT (
        CONCAT(inactive, inactive_ws) = '11'
        AND archived_at IS NOT NULL
    )
    AND (
        /* create user */
        [user_id] IS NULL
        /* update user */
        OR ISNULL(inactive, '') <> ISNULL(inactive_ws, '')
        OR ISNULL(coach_id, '') <> ISNULL(coach_id_ws, '')
        OR ISNULL(school_id, '') <> ISNULL(school_id_ws, '')
        OR ISNULL(grade_id, '') <> ISNULL(grade_id_ws, '')
        OR ISNULL(course_id, '') <> ISNULL(course_id_ws, '')
        OR ISNULL(role_id, '') <> ISNULL(role_id_ws, '')
        OR ISNULL(user_email, '') <> ISNULL(user_email_ws, '')
        OR ISNULL([user_name], '') <> ISNULL(user_name_ws, '')
        OR ISNULL(group_type, '') <> ISNULL(group_type_ws, '')
    )
