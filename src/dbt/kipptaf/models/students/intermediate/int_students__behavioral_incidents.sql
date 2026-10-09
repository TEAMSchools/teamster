-- trunk-ignore(sqlfluff/AM04): passes through every int_deanslist__incidents column
select i.*, loc.location_key,
from {{ ref("int_deanslist__incidents") }} as i
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on i.school_id = loc.deanslist_school_id
    and not loc.is_pathways
    and loc.location_name <> 'KIPP Whittier Elementary'
