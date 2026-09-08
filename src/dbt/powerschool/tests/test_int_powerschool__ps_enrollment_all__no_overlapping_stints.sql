with
    stints as (
        select
            studentid,
            student_number,
            schoolid,
            entrydate,
            exitdate,
            max(exitdate) over (
                partition by studentid, schoolid
                order by entrydate
                rows between unbounded preceding and 1 preceding
            ) as prior_max_exitdate,
        from {{ ref("int_powerschool__ps_enrollment_all") }}
        where entrydate is not null
    )

select studentid, student_number, schoolid, entrydate, exitdate, prior_max_exitdate,
from stints
where entrydate < prior_max_exitdate
