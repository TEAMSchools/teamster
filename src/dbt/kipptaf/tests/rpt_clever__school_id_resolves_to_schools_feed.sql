-- Every school_id shipped in the enrollments, sections, teachers and staff
-- Clever feeds must resolve to a row in schools.csv. A region filtered out of
-- one feed but not another lands here, which is exactly how the Paterson and
-- Miami leaks shipped rows pointing at schools Clever had never been told about.
-- school_id 0 is a valid target -- rpt_clever__schools supplies the District
-- Office via its hardcoded union branch.
with
    feed_school_ids as (
        select 'enrollments' as feed, cast(school_id as string) as school_id,
        from {{ ref("rpt_clever__enrollments") }}

        union all

        select 'sections' as feed, cast(school_id as string) as school_id,
        from {{ ref("rpt_clever__sections") }}

        union all

        select 'teachers' as feed, cast(school_id as string) as school_id,
        from {{ ref("rpt_clever__teachers") }}

        union all

        select 'staff' as feed, cast(school_id as string) as school_id,
        from {{ ref("rpt_clever__staff") }}
    )

select f.feed, f.school_id, count(*) as orphan_rows,
from feed_school_ids as f
left join {{ ref("rpt_clever__schools") }} as sch on f.school_id = sch.school_id
where sch.school_id is null
group by f.feed, f.school_id
