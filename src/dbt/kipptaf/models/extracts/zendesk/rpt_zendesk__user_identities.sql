with
    users_unpivot as (
        select
            user_id,
            name_column,
            `value`,

            if(name_column = 'email', true, false) as `primary`,
        from
            {{ ref("rpt_zendesk__users") }} unpivot (
                `value` for name_column
                in (email, mail_alias, personal_email, google_email)
            )
    )

select
    s.user_id,
    s.value,
    s.primary,

    ui.id as user_identity_id,

    if(ui.id is null, true, false) as is_create,

    if(s.primary and not ui.primary, true, false) as change_primary,

    false as is_delete,
from users_unpivot as s
left join
    {{ source("zendesk", "user_identities") }} as ui
    on s.user_id = ui.user_id
    and s.value = ui.value

union distinct

select
    ui.user_id,
    ui.value,
    ui.primary,
    ui.id as user_identity_id,

    false as is_create,
    false as change_primary,
    true as is_delete,
from {{ source("zendesk", "user_identities") }} as ui
left join users_unpivot as s on ui.user_id = s.user_id and ui.value = s.value
where s.user_id is null
