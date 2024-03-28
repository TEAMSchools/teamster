select
    swd.local_student_id as student_number,
    swd.date_administered,
    swd.field_label as word,

    rt.name as term_name,
    case
        swd.`value`
        when 'yes'
        then 'Mastered'
        when 'no'
        then 'Not Mastered'
        when 'retested'
        then 'Retested'
    end as mastery_status,
    case
        swd.`value` when 'yes' then 1 when 'retested' then 1 when 'no' then 0
    end as is_mastery,
from {{ ref("base_illuminate__repository_data") }} as swd
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on swd.date_administered between rt.start_date and rt.end_date
    and rt.type = 'RT'
    and rt.school_id = 0
where
    swd.scope = 'Sight Words Quiz'
    and swd.date_administered >= date({{ var("current_academic_year") }}, 7, 1)
