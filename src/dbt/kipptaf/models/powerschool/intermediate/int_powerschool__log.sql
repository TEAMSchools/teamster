select
    log.dcid,
    log.logtypeid,
    log.entry_date,
    log.entry,
    log.academic_year,

    gen.name as log_type,

    s.student_number,

    initcap(regexp_extract(log._dbt_source_relation, r'kipp(\w+)_')) as region
from {{ ref("stg_powerschool__log") }} as `log`
inner join
    {{ ref("stg_powerschool__gen") }} as gen
    on log.logtypeid = gen.id
    and gen.cat = 'logtype'
inner join
    {{ ref("stg_powerschool__students") }} as s
    on log.studentid = s.id
    and {{ union_dataset_join_clause(left_alias="log", right_alias="s") }}
