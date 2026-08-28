-- Tripwire for the provisional `false as is_out_of_district` in
-- int_students__student_enrollments (#5041). Every Miami student's custom_863
-- is the Z default or null today; its age 6-21 codes are out-of-district
-- placements, so any other code makes that literal silently wrong. Keyed on
-- the option code, not the label, because the labels are Focus-editable prose.
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
    and coalesce(opt.code, '?') not in ('Z', 'N/A')
