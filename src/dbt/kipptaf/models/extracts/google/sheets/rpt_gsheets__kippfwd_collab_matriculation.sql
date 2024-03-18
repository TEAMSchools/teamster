with
    ccdm_collab as (
        select
            kt.contact_id,
            kt.last_name,
            kt.first_name,
            kt.ktc_cohort as cohort,

            ap.id,
            ap.name,
            ap.matriculation_decision,
            ap.type,
            ap.intended_degree_type,

            coalesce(cn.ccdm, 0) as ccdm_complete,
            row_number() over (
                partition by ap.applicant order by ap.id asc
            ) as rn_applicant,
        from {{ ref("int_kippadb__roster") }} as kt
        left join
            {{ ref("stg_kippadb__application") }} as ap
            on (kt.contact_id = ap.applicant)
        left join
            {{ ref("int_kippadb__contact_note_rollup") }} as cn
            on (kt.contact_id = cn.contact_id)
        where
            ap.matriculation_decision = 'Matriculated (Intent to Enroll)'
            and cn.academic_year = {{ var("current_academic_year") }}
    )
    
select
    contact_id,
    last_name,
    first_name,
    cohort,
    id,
    name,
    matriculation_decision,
    type,
    intended_degree_type,
    ccdm_complete,
from ccdm_collab
where rn_applicant = 1
