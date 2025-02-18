{% set src_model = source("illuminate", "repositories") %}

select
    {{
        dbt_utils.star(
            from=src_model,
            relation_alias="a",
            except=["_fivetran_deleted", "_fivetran_synced", "deleted_at"],
        )
    }},

    u.local_user_id as creator_local_user_id,
    u.username as creator_username,
    u.first_name as creator_first_name,
    u.last_name as creator_last_name,
    u.email1 as creator_email_1,

    ds.code_translation as scope,

    dsa.code_translation as subject_area,
from {{ src_model }} as a
inner join
    {{ source("illuminate", "users") }} as u
    on a.user_id = u.user_id
    and not u._fivetran_deleted
left join
    {{ source("illuminate", "dna_scopes") }} as ds
    on a.code_scope_id = ds.code_id
    and not ds._fivetran_deleted
left join
    {{ source("illuminate", "dna_subject_areas") }} as dsa
    on a.code_subject_area_id = dsa.code_id
    and not dsa._fivetran_deleted
where not a._fivetran_deleted and a.deleted_at is null
