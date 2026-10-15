with
    stored_ranked as (
        select
            studentid,
            schoolid,
            academic_year,
            cumulative_y1_gpa,
            cumulative_y1_gpa_unweighted,

            row_number() over (
                partition by studentid, schoolid order by academic_year desc
            ) as rn,
        from {{ ref("int_powerschool__gpa_cumulative_year") }}
        where not is_projected
    )

select
    sr.studentid,
    sr.schoolid,
    sr.academic_year,
    sr.cumulative_y1_gpa,
    sr.cumulative_y1_gpa_unweighted,

    gc.cumulative_y1_gpa as gpa_cumulative_weighted,
    gc.cumulative_y1_gpa_unweighted as gpa_cumulative_unweighted,
from stored_ranked as sr
inner join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on sr.studentid = gc.studentid
    and sr.schoolid = gc.schoolid
where
    sr.rn = 1
    and not exists (
        select 1,
        from {{ ref("stg_powerschool__storedgrades") }} as sg
        where
            sr.studentid = sg.studentid
            and sr.schoolid = sg.schoolid
            and sg.storecode = 'Y1'
            and sg.academic_year = {{ var("current_academic_year") }}
    )
    /* 0.015, not 0.01: a rounding-boundary flip stores values exactly 0.01 apart,
       and float64 abs(2.97 - 2.96) > 0.01; 0.015 passes the one-cent flip while
       still catching any real drift (>= 0.02) */
    and (
        abs(coalesce(sr.cumulative_y1_gpa, -99) - coalesce(gc.cumulative_y1_gpa, -99))
        > 0.015
        or abs(
            coalesce(sr.cumulative_y1_gpa_unweighted, -99)
            - coalesce(gc.cumulative_y1_gpa_unweighted, -99)
        )
        > 0.015
    )
