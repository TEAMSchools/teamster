with
    latest_stored as (
        select
            studentid,
            schoolid,
            academic_year,
            cumulative_y1_gpa,
            cumulative_y1_gpa_unweighted,
        from {{ ref("int_powerschool__gpa_cumulative_year") }}
        where not is_projected
        qualify
            row_number() over (
                partition by studentid, schoolid order by academic_year desc
            )
            = 1
    )

select
    ls.studentid,
    ls.schoolid,
    ls.academic_year,
    ls.cumulative_y1_gpa,
    ls.cumulative_y1_gpa_unweighted,

    gc.cumulative_y1_gpa as gpa_cumulative_weighted,
    gc.cumulative_y1_gpa_unweighted as gpa_cumulative_unweighted,
from latest_stored as ls
inner join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on ls.studentid = gc.studentid
    and ls.schoolid = gc.schoolid
where
    not exists (
        select 1,
        from {{ ref("stg_powerschool__storedgrades") }} as sg
        where
            ls.studentid = sg.studentid
            and ls.schoolid = sg.schoolid
            and sg.storecode = 'Y1'
            and sg.academic_year = {{ var("current_academic_year") }}
    )
    /* 0.015, not 0.01: a rounding-boundary flip stores values exactly 0.01 apart,
       and float64 abs(2.97 - 2.96) > 0.01; 0.015 passes the one-cent flip while
       still catching any real drift (>= 0.02) */
    and (
        abs(coalesce(ls.cumulative_y1_gpa, -99) - coalesce(gc.cumulative_y1_gpa, -99))
        > 0.015
        or abs(
            coalesce(ls.cumulative_y1_gpa_unweighted, -99)
            - coalesce(gc.cumulative_y1_gpa_unweighted, -99)
        )
        > 0.015
    )
