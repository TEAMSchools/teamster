with
    termbins_quarters as (
        select
            t.schoolid,
            t.yearid,
            t.academic_year,

            tb.storecode as term,
            tb.date1 as term_start_date,
            tb.date2 as term_end_date,

            if(tb.storecode in ('Q1', 'Q2'), 'S1', 'S2') as semester,
        from {{ ref("stg_powerschool__terms") }} as t
        inner join
            {{ ref("stg_powerschool__termbins") }} as tb
            on t.id = tb.termid
            and t.schoolid = tb.schoolid
            and tb.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
        where t.isyearrec = 1 and t.schoolid != 0
    ),

    terms_quarters as (
        select
            t.schoolid,
            t.yearid,
            t.academic_year,
            t.semester,
            t.abbreviation as term,
            t.firstday as term_start_date,
            t.lastday as term_end_date,

            tb.term as termbins_term,
        from {{ ref("stg_powerschool__terms") }} as t
        left join
            termbins_quarters as tb
            on t.schoolid = tb.schoolid
            and t.yearid = tb.yearid
            and t.abbreviation = tb.term
        -- No isyearrec filter: the quarter records this branch reads carry
        -- isyearrec = 0. It is the year-long record, filtered above, that the
        -- termbins branch joins FROM.
        where t.abbreviation in ('Q1', 'Q2', 'Q3', 'Q4') and t.schoolid != 0
    ),

    all_quarters as (
        select
            schoolid,
            yearid,
            academic_year,
            term,
            term_start_date,
            term_end_date,
            semester,
        from termbins_quarters

        union all

        select
            schoolid,
            yearid,
            academic_year,
            term,
            term_start_date,
            term_end_date,
            semester,
        from terms_quarters
        where termbins_term is null
    )

select
    schoolid,
    yearid,
    academic_year,
    term,
    term_start_date,
    term_end_date,
    semester,

    if(
        current_date('{{ var("local_timezone") }}')
        between term_start_date and term_end_date,
        true,
        false
    ) as is_current_term,
from all_quarters
