-- distinct is grain projection, not dup-masking. stg_focus__attendance_calendar
-- carries 1,555 exact duplicate rows (15,067 raw against 13,512 distinct
-- (school_id, syear, school_date) keys; including `minutes` still yields 13,512, so
-- the duplication is total). Every column below derives from that key, so identical
-- tuples collapse with no information loss. Without it this model breaks its own
-- (schoolid, academic_year, school_date) grain and double-counts in-session days in
-- dim_school_calendars, which is not year-scoped. AY2026 happens to be clean; the
-- duplicates are all in historical years. Same source and same fix as Task 1.
select distinct
    school_id as schoolid,
    school_date,
    syear as academic_year,

    date_trunc(school_date, week) as week_start_date,
    date_add(date_trunc(school_date, week), interval 6 day) as week_end_date,
from
    {{ ref("stg_focus__attendance_calendar") }}
    -- Focus has no insession flag or membership-value concept. A row in
    -- attendance_calendar IS an in-session day -- that is this model's whole
    -- meaning, so no constant column is needed to express it. Five schools
    -- (2 closed, 3 non-instructional) carry unfiltered 212-day calendars
    -- including holidays; that is a Focus configuration problem handed to Ops,
    -- not something filtered here. The warn test in the kipptaf union
    -- surfaces the rows. week_start_date is the Sunday, week_end_date the
    -- following Saturday.
