-- trunk-ignore-all(sqlfluff): Focus SIS PostgreSQL, not the repo's BigQuery dialect
-- trunk-ignore-all(sqlfmt): would mangle Focus {VARIABLE} placeholders
-- District Report starter skeleton — Focus SIS (PostgreSQL)
-- Adapt table names, joins, and variables to the actual report.
-- Delete this comment block before pasting into the Focus Edit panel.

-- Variables to define via Edit Variables before this query validates:
--   {ENTITY_FILTER}   Pull-down (Multiple) Query  -- defaults to all selected
--   {GRADE_LEVEL}     Pull-down (Multiple) Query  -- see school_gradelevels query below
--   {SEARCH_ID}       Text                        -- optional exact-ID filter
--   {START_DATE}      Date                        -- optional range start
--   {END_DATE}        Date                        -- optional range end

-- Example Pull-down (Multiple) Query for a lookup-table filter:
-- select
--     title,
--     id as value
-- from <lookup_table>
-- where deleted is null  -- or deleted_at is null; confirm the real soft-delete column
-- order by title

-- Example Pull-down (Multiple) Query for Grade Level (grade lives on enrollment, not students):
-- select
--     short_name as title,
--     id as value
-- from school_gradelevels
-- where school_id = {school_id}
-- order by short_name

select
    s.student_id,
    s.last_name,
    s.first_name,
    sg.short_name as grade_level,
    sc.title as school

    -- add aggregates here, e.g.:
    -- , count(x.id) as record_count
    -- , coalesce(sum(x.value), 0) as total_value

from students s
join student_enrollment se
    on s.student_id = se.student_id
   and se.syear = {syear}
   and se.school_id = {school_id}
   -- current_date returns nothing for a past {syear}; see the reference file
   and se.start_date <= current_date
   and (se.end_date is null or se.end_date >= current_date)
   and (se.custom_9 is null or se.custom_9 = 'N')
join schools sc
    on se.school_id = sc.id
left join school_gradelevels sg
    on se.grade_id = sg.id

-- left join the entity table this report is really about, e.g.:
-- left join <entity_table> x
--     on x.student_id = s.student_id
--    and x.deleted is null
--    and x.behavior_id in ({ENTITY_FILTER})           -- filters affecting the LEFT-joined
--    and (nullif('{START_DATE}', '') is null           -- table go in its ON clause, not WHERE,
--         or x.record_date >= nullif('{START_DATE}', '')::date)   -- or students with zero matches disappear
--    and (nullif('{END_DATE}', '') is null
--         or x.record_date <= nullif('{END_DATE}', '')::date)

where s.deleted is null
  and se.grade_id in ({GRADE_LEVEL})
  and (nullif('{SEARCH_ID}', '') is null or s.student_id = nullif('{SEARCH_ID}', '')::bigint)

-- group by is only needed once an aggregate is added above:
-- group by s.student_id, s.last_name, s.first_name, sg.short_name, sc.title
;
