with
    fast_concat as (
        select
            student_id,
            academic_year,

            concat(achievement_level, ' (', scale_score, ')') as fast_score,
            lower(concat(discipline, '_', administration_window)) as pivot_column,
        from {{ ref("stg_fldoe__fast") }}
    ),

    fast_pivot as (
        select
            student_id,
            academic_year,
            ela_pm1,
            ela_pm2,
            ela_pm3,
            math_pm1,
            math_pm2,
            math_pm3,
        from
            fast_concat pivot (
                max(fast_score) for pivot_column
                in ('ela_pm1', 'ela_pm2', 'ela_pm3', 'math_pm1', 'math_pm2', 'math_pm3')
            )
    ),

    /* TODO(#4794): int_focus__student_enrollments.enroll_status derives from
       drop-code presence, and Focus stamps W01/W02 rollover codes on nearly
       every span at year end -- it reads 361 of 365 AY2025 students as
       transferred out. Derive locally until that is fixed upstream, then
       delete this CTE and read the upstream column. */
    open_enrollment as (
        select distinct student_number,
        from {{ ref("int_focus__student_enrollments") }}
        where academic_year = {{ var("current_academic_year") }} and exitcode is null
    ),

    contact_1 as (
        select student_id, contact_name, email, phone_home, phone_mobile,
        from {{ ref("int_focus__student_contacts") }}
        where sort_order = 1
    ),

    contact_2 as (
        select student_id, contact_name, email, phone_home, phone_mobile,
        from {{ ref("int_focus__student_contacts") }}
        where sort_order = 2
    ),

    students as (
        select
            student_id,
            powerschool_id,
            sex_label,
            ese_fefp_code,
            cast(disis_id as string) as mdcps_id_raw,
        from {{ ref("int_focus__students") }}
    ),

    /* gpa_y1 is PowerSchool-only. Keep the is_current filter and join THIS
       CTE, never the raw ref -- int_powerschool__gpa_term carries superseded
       term rows, and a direct join to the raw ref fanned prod out to 1,274
       rows for 365 students. */
    gpa_term as (
        select _dbt_source_project, studentid, yearid, schoolid, gpa_y1,
        from {{ ref("int_powerschool__gpa_term") }}
        where is_current
    )

select
    e.academic_year,
    e.student_name as lastfirst,

    /* advisor_lastfirst, gpa_cumulative, gpa_y1, and iep_status are
       hybrid-sourced: PowerSchool (via psy/gpa) for the years PowerSchool
       covers, Focus for AY2026 onward. No explicit year gate is needed --
       PowerSchool holds no Miami AY2026 row, so the same-year psy join
       naturally returns null there, and the hybrid ages out on its own as
       PowerSchool years fall off the two-year window. advisor_lastfirst and
       gpa_cumulative/gpa_y1 go null for Focus-era years pending #4795
       (advisor) and #4796 (GPA replacement). */
    psy.advisor_lastfirst,

    cast(s.powerschool_id as int64) as ps_id,

    lpad(s.mdcps_id_raw, 7, '0') as mdcps_id,

    regexp_extract(s.sex_label, r'\[(\w)\]') as gender,

    coalesce(
        psy.iep_status, if(s.ese_fefp_code is not null, 'Has IEP', 'No IEP')
    ) as iep_status,

    c1.contact_name as contact_1_name,
    c1.phone_home as contact_1_phone_home,
    c1.phone_mobile as contact_1_phone_mobile,
    c1.email as contact_1_email_current,

    c2.contact_name as contact_2_name,
    c2.phone_home as contact_2_phone_home,
    c2.phone_mobile as contact_2_phone_mobile,
    c2.email as contact_2_email_current,

    /* enroll_status mixes grains deliberately: 0 and 2 are student-level,
       mirroring PowerSchool's student-level enroll_status, while -1 and 3 are
       row-level (per enrollment span). Do not "fix" this by scoping
       open_enrollment to academic_year -- that reintroduces the bug this PR
       removes (see the open_enrollment CTE comment above). */
    case
        when e.startdate > current_date('{{ var("local_timezone") }}')
        /* Fires for the whole current academic year until the first day of
           school (Miami's is roughly Aug 17), then self-heals as
           enrollment startdates fall in the past. Until then, consumers
           filtering enroll_status = 0 see zero current-year students -- a
           deliberate, disclosed tradeoff, not a bug. */
        then -1
        when e.enroll_status = 3
        then 3
        when oe.student_number is not null
        then 0
        else 2
    end as enroll_status,

    e.grade_level,

    fp.ela_pm1,
    fp.ela_pm2,
    fp.ela_pm3,
    fp.math_pm1,
    fp.math_pm2,
    fp.math_pm3,

    psy.cumulative_y1_gpa_unweighted as gpa_cumulative,

    adap.unweighted_ada as previous_year_ada,

    e.fteid as fleid,

    gpa.gpa_y1,

    fp_prev.ela_pm3 as ela_pm3_prev,
    fp_prev.math_pm3 as math_pm3_prev,
from {{ ref("int_focus__student_enrollments") }} as e
left join students as s on e.student_number = s.student_id
left join open_enrollment as oe on e.student_number = oe.student_number
left join contact_1 as c1 on e.student_number = c1.student_id
left join contact_2 as c2 on e.student_number = c2.student_id
left join
    fast_pivot as fp on e.fteid = fp.student_id and e.academic_year = fp.academic_year
left join
    fast_pivot as fp_prev
    on e.fteid = fp_prev.student_id
    and e.academic_year - 1 = fp_prev.academic_year
left join
    {{ ref("int_extracts__student_enrollments") }} as adap
    on s.powerschool_id = adap.student_number
    and e.academic_year - 1 = adap.academic_year
    and adap.region = 'Miami'
    and adap.rn_year = 1
left join
    {{ ref("int_extracts__student_enrollments") }} as psy
    on s.powerschool_id = psy.student_number
    and e.academic_year = psy.academic_year
    and psy.region = 'Miami'
    and psy.rn_year = 1
left join
    gpa_term as gpa
    on psy.studentid = gpa.studentid
    and psy.yearid = gpa.yearid
    and psy.schoolid = gpa.schoolid
    and psy._dbt_source_project = gpa._dbt_source_project
where
    e.rn_year = 1
    and e.grade_level in (7, 8)
    and e.academic_year >= {{ var("current_academic_year") - 1 }}
