select
    s.school_id,
    cast(
        '''`teamster-332318.kippmiami_focus.int_focus__schools`''' as string
    ) as _dbt_source_relation,
from `teamster-332318`.`kippmiami_focus`.`stg_focus__schools` as s
where s.as_of = current_date('America/New_York')
