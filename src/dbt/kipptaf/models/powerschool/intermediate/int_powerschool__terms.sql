select
    t._dbt_source_relation,
    t.schoolid,
    t.yearid,
    t.academic_year,

    tb.storecode as term,
    tb.date1 as term_start_date,
    tb.date2 as term_end_date,

    if(tb.storecode in ('Q1', 'Q2'), 'S1', 'S2') as semester,

    if(
        current_date('{{ var("local_timezone") }}') between tb.date1 and tb.date2,
        true,
        false
    ) as is_current_term,
from {{ ref("stg_powerschool__terms") }} as t
inner join
    {{ ref("stg_powerschool__termbins") }} as tb
    on t.id = tb.termid
    and t.schoolid = tb.schoolid
    and {{ union_dataset_join_clause(left_alias="t", right_alias="tb") }}
    and tb.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
where t.isyearrec = 1
