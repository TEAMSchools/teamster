-- Focus marking periods, conformed to the network terms vocabulary. Progress
-- periods have no PowerSchool equivalent and are dropped; the remaining year,
-- semester and quarter rows match the archive's own 1 year + 2 semester +
-- 4 quarter set per school per year.
--
-- Floored at 2018, KIPP Miami's first school year. Focus carries a full
-- year/semester/quarter set for two schools in every syear back to 1980,
-- decades before any KIPP Miami school existed -- roughly 760 template rows
-- that would otherwise fabricate history.
select
    mp.marking_period_id,
    mp.school_id,
    mp.type,
    mp.title,
    mp.short_name,
    mp.start_date,
    mp.end_date,

    mp.syear as academic_year,

    if(mp.short_name in ('Q1', 'Q2'), 'S1', 'S2') as quarter_semester,

    current_date('{{ var("local_timezone") }}')
    between mp.start_date and mp.end_date as is_within_dates,
from {{ ref("stg_focus__marking_periods") }} as mp
where mp.type in ('year', 'semester', 'quarter') and mp.syear >= 2018
