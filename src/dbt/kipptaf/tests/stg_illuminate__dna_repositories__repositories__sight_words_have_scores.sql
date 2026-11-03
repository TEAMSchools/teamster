-- depends_on: {{ ref("stg_illuminate__dna_repositories__repositories") }}
with
    current_year_quizzes as (
        select repository_id, title, date_administered,
        from {{ ref("int_illuminate__repositories") }}
        where
            scope = 'Sight Words Quiz'
            and date_administered >= '{{ var("current_academic_year") }}-07-01'
    ),

    quizzes_with_scores as (
        -- grain projection, not dup-masking
        select distinct repository_id,
        from {{ ref("int_illuminate__repository_data") }}
        where scope = 'Sight Words Quiz'
    )

select q.repository_id, q.title, q.date_administered,
from current_year_quizzes as q
left join quizzes_with_scores as s on q.repository_id = s.repository_id
where
    s.repository_id is null
    -- a week for schools to enter scores before flagging
    and q.date_administered
    <= date_sub(current_date('{{ var("local_timezone") }}'), interval 7 day)
