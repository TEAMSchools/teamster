select
    id,
    course_period_id,
    teacher_id,
    imported,
    created_at,
    updated_at,

    cast(f as numeric) as f,
    cast(h as numeric) as h,
    cast(m as numeric) as m,
    cast(s as numeric) as s,
    cast(t as numeric) as t,
    cast(u as numeric) as u,
    cast(w as numeric) as w,
from {{ source("focus", "co_teacher_days") }}
