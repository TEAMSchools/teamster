with
    entry_cohort as (
        select co.school, co.student_number, 1 as is_entry_cohort

        from {{ ref("int_extracts__student_enrollments") }} as co
        where
            co.grade_level = 9
            and co.rn_year = 1
            and co.is_enrolled_oct01
            and co.year_in_school = 1
            and not co.is_retained_year
    ),

    transfer_in as (
        select co.student_number, co.school, 1 as is_transfer_in

        from {{ ref("int_extracts__student_enrollments") }} as co
        where
            (
                (co.grade_level between 10 and 12)
                or (
                    co.grade_level = 9
                    and (
                        extract(month from co.entrydate) > 10
                        or (
                            extract(month from co.entrydate) = 10
                            and extract(day from co.entrydate) > 1
                        )
                    )
                )
            )
            and co.rn_year = 1
            and co.year_in_school = 1
    ),

    transfer_out as (
        select co.student_number, co.school, 1 as is_transfer_out

        from {{ ref("int_extracts__student_enrollments") }} as co
        where
            co.rn_year = 1
            and co.rn_undergrad = 1
            and co.enroll_status = 2
            and (co.exitcode = 'D9' or co.exitcode like 'T%')
    ),

    grad_roster as (
        select distinct
            co.school,
            co.cohort,
            co.student_number,

            coalesce(ec.is_entry_cohort, 0) as is_entry_cohort,
            coalesce(ti.is_transfer_in, 0) as is_transfer_in,
            coalesce(tr.is_transfer_out, 0) as is_transfer_out,

            case
                when co.academic_year + 1 = co.cohort then 1 else 0
            end as is_cohort_grad_year,

            case
                when co.academic_year + 1 = co.cohort and co.exitcode = 'G1'
                then 1
                else 0
            end as is_4yr_grad

        from {{ ref("int_extracts__student_enrollments") }} as co
        left join
            entry_cohort as ec
            on (co.student_number = ec.student_number and co.school = ec.school)
        left join
            transfer_in as ti
            on (co.student_number = ti.student_number and co.school = ti.school)
        left join
            transfer_out as tr
            on (co.student_number = tr.student_number and co.school = tr.school)
        where co.school_level = 'HS' and co.rn_year = 1 and co.rn_undergrad = 1
    ),

    graduated as (
        select school_name, count(student_number) as total_grads,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            cohort = {{ var("current_academic_year") }}
            and academic_year = {{ var("current_academic_year") - 1 }}
            and grade_level != 99
            and not is_out_of_district
            and enroll_status = 3
        group by all
    )

select
    gr.cohort,
    gr.school,

    sum(gr.is_entry_cohort) as total_9_entry,

    sum(gr.is_transfer_in) as total_transfer_in,

    sum(gr.is_transfer_out) as total_transfer_out,

    (sum(gr.is_entry_cohort) + sum(gr.is_transfer_in))
    - sum(gr.is_transfer_out) as adjusted_cohort,

    sum(gr.is_4yr_grad) as total_4yr_grad,

    round(
        sum(gr.is_4yr_grad) / (
            (sum(gr.is_entry_cohort) + sum(gr.is_transfer_in)) - sum(gr.is_transfer_out)
        ),
        3
    ) as pct_grad

from grad_roster as gr
group by gr.cohort, gr.school
order by gr.cohort asc, gr.school asc
