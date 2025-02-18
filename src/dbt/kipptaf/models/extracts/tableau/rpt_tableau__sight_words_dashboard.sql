with
    swq as (
        select
            r.repository_id,
            r.title,
            r.date_administered,

            rt.name as term_name,
            rt.academic_year,

            f.label,

            g.grade_level,
        from {{ ref("int_illuminate__repositories") }} as r
        inner join
            {{ ref("stg_reporting__terms") }} as rt
            on r.date_administered between rt.start_date and rt.end_date
            and rt.type = 'RT'
            and rt.school_id = 0
        inner join
            {# {{ ref("stg_illuminate__repository_fields") }} as f #}
            {{ ref("stg_illuminate__dna_repositories__repository_fields") }} as f
            on r.repository_id = f.repository_id
        inner join
            {# {{ ref("stg_illuminate__repository_grade_levels") }} as g #}
            {{ ref("stg_illuminate__dna_repositories__repository_grade_levels") }} as g
            on r.repository_id = g.repository_id
        where r.scope = 'Sight Words Quiz'
    )

select
    swq.repository_id,
    swq.title,
    swq.date_administered,
    swq.term_name,
    swq.academic_year,
    swq.label as sight_word,

    co.student_number,
    co.student_name,
    co.region,
    co.schoolid,
    co.school,
    co.grade_level,
    co.advisory as team,
    co.is_self_contained as is_pathways,
    co.iep_status,
    co.lep_status,
    co.gifted_and_talented,
    co.gender,
    co.ethnicity,
    co.nj_student_tier,
    co.hos,

    sw.value,

    false as is_replacement,
from swq
inner join
    {{ ref("int_extracts__student_enrollments_subjects") }} as co
    on swq.academic_year = co.academic_year
    and swq.grade_level = co.grade_level
    and co.iready_subject = 'Reading'
left join
    {{ ref("int_illuminate__repository_data") }} as sw
    on swq.repository_id = sw.repository_id
    and swq.label = sw.field_label
    and co.student_number = sw.local_student_id

union all

select
    swq.repository_id,
    swq.title,
    swq.date_administered,
    swq.term_name,
    swq.academic_year,
    swq.label as sight_word,

    co.student_number,
    co.student_name,
    co.region,
    co.schoolid,
    co.school,
    co.grade_level,
    co.advisory as team,
    co.is_self_contained as is_pathways,
    co.iep_status,
    co.lep_status,
    co.gifted_and_talented,
    co.gender,
    co.ethnicity,
    co.nj_student_tier,
    co.hos,

    sw.value,

    true as is_replacement,
from swq
inner join
    {{ ref("int_illuminate__repository_data") }} as sw
    on swq.repository_id = sw.repository_id
    and swq.label = sw.field_label
inner join
    {{ ref("int_extracts__student_enrollments_subjects") }} as co
    on swq.academic_year = co.academic_year
    and swq.grade_level != co.grade_level
    and sw.local_student_id = co.student_number
    and co.is_enrolled_recent
    and co.iready_subject = 'Reading'
