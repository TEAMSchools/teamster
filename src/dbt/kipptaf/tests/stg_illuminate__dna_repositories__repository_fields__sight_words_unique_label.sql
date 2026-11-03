with
    duplicate_labels as (
        select repository_id, label, count(*) as n_fields,
        from {{ ref("stg_illuminate__dna_repositories__repository_fields") }}
        group by repository_id, label
        having count(*) > 1
    )

select
    dl.repository_id,
    dl.label,
    dl.n_fields,

    r.title,
    r.creator_local_user_id,
    r.creator_username,
    r.creator_first_name,
    r.creator_last_name,
    r.creator_email_1,
from duplicate_labels as dl
inner join
    {{ ref("int_illuminate__repositories") }} as r on dl.repository_id = r.repository_id
where r.scope = 'Sight Words Quiz'
