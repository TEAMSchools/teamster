-- grain projection, not dup-masking. `stg_focus__attendance_calendar` carries
-- 1,555 exact duplicate rows: 15,067 raw against 13,512 distinct (`school_id`,
-- `syear`, `school_date`) keys, and including `minutes` still yields 13,512, so
-- the duplication is total. Every column below derives from that key, so
-- identical tuples collapse with no loss. Without the `distinct` this model
-- breaks its own (`schoolid`, `academic_year`, `school_date`) grain and
-- double-counts in-session days in `dim_school_calendars`, which is not
-- year-scoped. The duplicates all sit in historical years; AY2026 is clean.
select distinct
    school_id as schoolid,
    school_date,
    syear as academic_year,

    date_trunc(school_date, week) as week_start_date,
    date_add(date_trunc(school_date, week), interval 6 day) as week_end_date,
from {{ ref("stg_focus__attendance_calendar") }}
