select
    kt.contact_id,
    kt.last_name,
    kt.first_name,
    ap.id,
    ap.name,
    ap.matriculation_decision,
    coalesce(cn.ccdm, 0) as ccdm_complete,
    count(*) over (partition by ap.applicant order by ap.id asc) as row_count,
    ap.type,
    ap.intended_degree_type,

from {{ ref("int_kippadb__roster") }} as kt
left join {{ ref("stg_kippadb__application") }} as ap on (kt.contact_id = ap.applicant)
left join
    {{ ref("int_kippadb__contact_note_rollup") }} as cn
    on (kt.contact_id = cn.contact_id)
where
    ap.matriculation_decision = 'Matriculated (Intent to Enroll)'
    and cn.academic_year = 2023
