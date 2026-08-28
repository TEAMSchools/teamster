-- Guards the custom_863 decode that drives is_out_of_district and its three
-- companion columns in int_students__student_enrollments (#5041). Every option
-- must be one the derivation classifies: C, D, F, H and P are out-of-district
-- placements, Z and N/A are no placement. Anything else is one of Florida's
-- age 3-5 options, excluded because Miami enrolls no pre-K -- if one appears,
-- the student reports as in-district on an unexamined assumption. Keyed on the
-- option code, not the label, because the labels are Focus-editable prose.
-- Left join so a stored value that resolves to no option fails too. Any
-- returned row is a warning.
select stu.student_id, stu.idea_educational_environment, opt.code, opt.label,
from {{ ref("stg_focus__students") }} as stu
left join
    {{ ref("int_focus__custom_field_options") }} as opt
    on cast(stu.idea_educational_environment as string) in (opt.option_id, opt.code)
    and opt.column_name = 'custom_863'
    and opt.source_class = 'SISStudent'
where
    stu.idea_educational_environment is not null
    and coalesce(opt.code, '?') not in ('Z', 'N/A', 'C', 'D', 'F', 'H', 'P')
