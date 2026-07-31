with
    schools as (
        -- Same filter as rpt_parentsquare__schools so a staff row can never
        -- reference a school the schools feed omits.
        select cast(school_number as string) as school_id,
        from {{ ref("stg_powerschool__schools") }}
        where _dbt_source_project = 'kippnewark' and state_excludefromreporting = 0
    ),

    ops_leaders as (
        -- The phase-1 ParentSquare user population is the six named regional
        -- Operations leaders from the KIPP NJ + ParentSquare Integration Planner
        -- (question 4: "Regional Operation leaders ... No school staff, no
        -- teachers, etc"). There is no title or department rule that isolates
        -- exactly these six — the regional Operations group at school_id 0 holds
        -- twelve people across eight titles, and the planner picks a subset — so
        -- the roster is matched on KIPP mail, which is also the key ParentSquare
        -- matches a staff user on (planner question 8: access is via the KIPP
        -- Google account). Move this to an Ops-managed Google Sheet source if the
        -- list starts churning.
        select employee_number, job_title, given_name, family_name_1, mail,
        from {{ ref("int_people__staff_roster") }}
        where
            lower(mail) in (
                'eamato@kippnj.org',
                'lreynolds@kippnj.org',
                'yesteban@kippnj.org',
                'rfletcher@kippnj.org',
                'agewirtz@kippnj.org',
                'mcassells@kippteamandfamily.org'
            )
            and worker_status_code != 'Terminated'
            and not is_prestart
    )

-- One row per (leader, school). ParentSquare's staff file is per-school and its
-- spec states a staff member "can be at more than one school", so fanning the six
-- across every Newark school is what grants them school-level access everywhere —
-- and it is what makes every rpt_parentsquare__sections.staff_id resolve at its
-- own school. No district-office row is emitted because schools.csv carries only
-- the twelve operating schools, so a school_id of 0 would dangle.
select
    o.job_title as title,
    o.given_name as first_name,
    o.family_name_1 as last_name,
    o.mail as email,

    s.school_id,

    cast(o.employee_number as string) as staff_id,
from ops_leaders as o
cross join schools as s
