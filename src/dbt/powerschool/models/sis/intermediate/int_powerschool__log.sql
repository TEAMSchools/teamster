select
    log.studentid,
    log.dcid,
    log.logtypeid,
    log.entry_date,
    log.entry,

    gen.name as log_type,

    if(
        extract(month from log.entry_date) >= 7,
        extract(year from log.entry_date),
        extract(year from log.entry_date) - 1
    ) as academic_year,
from {{ ref("stg_powerschool__log") }} as `log`
inner join
    {{ ref("stg_powerschool__gen") }} as gen
    on log.logtypeid = gen.id
    and gen.cat = 'logtype'
