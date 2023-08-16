with
    storedgrades_points as (
        select
            sg.academic_year,

            s.student_number,

            cast(sg.potentialcrhrs as numeric) as potentialcrhrs,
            cast(sg.potentialcrhrs as numeric)
            * cast(sg.gpa_points as numeric) as weighted_points,

            cast(sg.potentialcrhrs as numeric)
            * cast(suw.grade_points as numeric) as unweighted_points,
        from {{ ref("stg_powerschool__storedgrades") }} as sg
        inner join
            {{ ref("stg_powerschool__students") }} as s
            on sg.studentid = s.id
            and {{ union_dataset_join_clause(left_alias="sg", right_alias="s") }}
        left outer join
            {{ ref("int_powerschool__gradescaleitem_lookup") }} as suw
            on {{ union_dataset_join_clause(left_alias="sg", right_alias="suw") }}
            and sg.percent between suw.min_cutoffpercentage and suw.max_cutoffpercentage
            and sg.gradescale_name_unweighted = suw.gradescale_name
        where sg.storecode = 'Y1' and sg.excludefromgpa = 0
    ),

    points_rollup as (
        select
            student_number,
            academic_year,
            sum(weighted_points) as weighted_points,
            sum(unweighted_points) as unweighted_points,
            nullif(sum(potentialcrhrs), 0) as credit_hours,
        from storedgrades_points
        group by student_number, academic_year
    )

select
    student_number,
    academic_year,
    round(weighted_points / credit_hours, 2) as `GPA_Y1_weighted`,
    round(unweighted_points / credit_hours, 2) as `GPA_Y1_unweighted`,
from points_rollup

union all

select
    co.student_number,

    null as academic_year,

    sg.cumulative_y1_gpa as `GPA_Y1_weighted`,
    sg.cumulative_y1_gpa_unweighted as `GPA_Y1_unweighted`,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("int_powerschool__gpa_cumulative") }} as sg
    on co.studentid = sg.studentid
    and co.schoolid = sg.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="sg") }}
where co.rn_undergrad = 1
