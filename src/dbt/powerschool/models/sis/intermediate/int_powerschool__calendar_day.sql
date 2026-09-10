select
    cd.*,

    t.yearid,
    t.academic_year,

    sch.name as school_name,
    sch.abbreviation as school_abbreviation,
    sch.school_level,
    sch.schoolcity,
from {{ ref("stg_powerschool__calendar_day") }} as cd
/* left join: a day with no covering year term keeps flowing with a null year,
   which is what kipptaf's int_students__calendar_day does today */
left join
    {{ ref("stg_powerschool__terms") }} as t
    on cd.schoolid = t.schoolid
    and cd.date_value between t.firstday and t.lastday
    and t.isyearrec = 1
left join
    {{ ref("stg_powerschool__schools") }} as sch on cd.schoolid = sch.school_number
