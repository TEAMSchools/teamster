select
    log._dbt_source_relation,
    log._dbt_source_project,
    log.studentid,
    log.dcid,
    log.logtypeid,
    log.entry_date,
    log.entry,
    log.academic_year,

    gen.name as log_type,
from {{ ref("stg_powerschool__log") }} as `log`
inner join
    {{ ref("stg_powerschool__gen") }} as gen
    on log.logtypeid = gen.id
    and gen.cat = 'logtype'
    and log._dbt_source_project = gen._dbt_source_project
