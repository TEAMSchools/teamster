select
    a.* except (deleted_at),

    u.local_user_id as creator_local_user_id,
    u.username as creator_username,
    u.first_name as creator_first_name,
    u.last_name as creator_last_name,
    u.email1 as creator_email_1,

    ds.code_translation as scope,

    dsa.code_translation as subject_area,
from {{ ref("stg_illuminate__dna_repositories__repositories") }} as a
inner join {{ ref("stg_illuminate__public__users") }} as u on a.user_id = u.user_id
left join
    {{ ref("stg_illuminate__codes__dna_scopes") }} as ds on a.code_scope_id = ds.code_id
left join
    {{ ref("stg_illuminate__codes__dna_subject_areas") }} as dsa
    on a.code_subject_area_id = dsa.code_id
where a.deleted_at is null
