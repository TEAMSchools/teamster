-- Guards the corrected decode join: known in-scope fields must resolve to
-- options. Returns offending (source_class, column_name) rows -> any row fails.
with
    expected as (
        select 'SISSchool' as source_class, 'custom_100000004' as column_name,
        union all
        select 'SISStudent' as source_class, 'custom_200000000' as column_name,
        union all
        select 'StudentEnrollment' as source_class, 'custom_4' as column_name,
    )
select expected.source_class, expected.column_name,
from expected
left join
    {{ ref("int_focus__custom_field_options") }} as o
    on expected.source_class = o.source_class
    and expected.column_name = o.column_name
where o.option_id is null
