select
    r.repository_id,
    r.title,
    r.date_administered,

    rt.name as term_name,
    rt.academic_year,

    f.label as sight_word,

    co.student_number,
    co.lastfirst,
    co.region,
    co.reporting_schoolid,
    co.grade_level,
    co.advisory_name as team,
    co.is_self_contained as is_pathways,
    co.spedlep as iep_status,
    co.lep_status,
    co.gender,
    co.ethnicity,

    sw.`value`,

    false as is_replacement,
from {{ ref("base_illuminate__repositories") }} as r
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on r.date_administered between rt.start_date and rt.end_date
    and rt.type = 'RT'
    and rt.school_id = 0
inner join
    {{ ref("stg_illuminate__repository_fields") }} as f
    on r.repository_id = f.repository_id
inner join
    {{ ref("stg_illuminate__repository_grade_levels") }} as g
    on r.repository_id = g.repository_id
inner join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on g.grade_level = co.grade_level
    and rt.academic_year = co.academic_year
    and co.is_enrolled_recent
    and co.rn_year = 1
left join
    {{ ref("base_illuminate__repository_data") }} as sw
    on co.student_number = sw.local_student_id
    and r.repository_id = sw.repository_id
    and f.label = sw.field_label
where r.scope = 'Sight Words Quiz'

union all

select
    r.repository_id,
    r.title,
    r.date_administered,

    rt.name as term_name,
    rt.academic_year,

    f.label as sight_word,

    co.student_number,
    co.lastfirst,
    co.region,
    co.reporting_schoolid,
    co.grade_level,
    co.advisory_name as team,
    co.is_self_contained as is_pathways,
    co.spedlep as iep_status,
    co.lep_status,
    co.gender,
    co.ethnicity,

    sw.`value`,

    true as is_replacement,
from {{ ref("base_illuminate__repositories") }} as r
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on r.date_administered between rt.start_date and rt.end_date
    and rt.type = 'RT'
    and rt.school_id = 0
inner join
    {{ ref("stg_illuminate__repository_fields") }} as f
    on r.repository_id = f.repository_id
inner join
    {{ ref("stg_illuminate__repository_grade_levels") }} as g
    on r.repository_id = g.repository_id
inner join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on g.grade_level != co.grade_level
    and rt.academic_year = co.academic_year
    and co.is_enrolled_recent
    and co.rn_year = 1
inner join
    {{ ref("base_illuminate__repository_data") }} as sw
    on co.student_number = sw.local_student_id
    and r.repository_id = sw.repository_id
    and f.label = sw.field_label
where r.scope = 'Sight Words Quiz'
