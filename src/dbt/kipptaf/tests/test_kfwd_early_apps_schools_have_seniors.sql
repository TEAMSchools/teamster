select sc.overgrad_school_name,
from {{ ref("stg_google_sheets__kfwd__early_apps_schools") }} as sc
left join
    {{ ref("int_overgrad__students") }} as s
    on sc.overgrad_school_name = s.school__name
    and s.graduation_year = {{ var("current_academic_year") + 1 }}
where s.id is null
