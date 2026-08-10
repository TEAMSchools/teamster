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
       delete these two CTEs and read the upstream column. Anchor on the max
       academic_year in Focus, NOT var("current_academic_year"), which lags the
       July rollover. */
    latest_year as (
        select max(academic_year) as academic_year,
        from {{ ref("int_focus__student_enrollments") }}
    ),

    open_enrollment as (
        select distinct e.student_number,
        from {{ ref("int_focus__student_enrollments") }} as e
        inner join latest_year as ly on e.academic_year = ly.academic_year
        where e.exitcode is null
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
    )

-- trunk-ignore(sqlfluff/ST06): select order is the Google Sheet column order
select
    e.academic_year,
    e.student_name as lastfirst,

    /* TODO(#4795): Focus has no advisory structure for grades 7-8 */
    cast(null as string) as advisor_lastfirst,

    cast(s.powerschool_id as int64) as ps_id,

    lpad(cast(s.disis_id as string), 7, '0') as mdcps_id,

    regexp_extract(s.sex_label, r'\[(\w)\]') as gender,

    if(s.ese_fefp_code is not null, 'Has IEP', 'No IEP') as iep_status,

    c1.contact_name as contact_1_name,
    c1.phone_home as contact_1_phone_home,
    c1.phone_mobile as contact_1_phone_mobile,
    c1.email as contact_1_email_current,

    c2.contact_name as contact_2_name,
    c2.phone_home as contact_2_phone_home,
    c2.phone_mobile as contact_2_phone_mobile,
    c2.email as contact_2_email_current,

    case
        when e.startdate > current_date('{{ var("local_timezone") }}')
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

    /* TODO(#4796): Miami middle school no longer produces a GPA; awaiting a
       replacement academic-standing metric from KIPP Forward */
    cast(null as float64) as gpa_cumulative,

    ada.ada_unweighted_year_prev as previous_year_ada,

    e.fteid as fleid,

    /* TODO(#4796): see gpa_cumulative above */
    cast(null as float64) as gpa_y1,

    fp_prev.ela_pm3 as ela_pm3_prev,
    fp_prev.math_pm3 as math_pm3_prev,
from {{ ref("int_focus__student_enrollments") }} as e
left join {{ ref("int_focus__students") }} as s on e.student_number = s.student_id
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
    {{ ref("int_extracts__student_enrollments") }} as ada
    on s.powerschool_id = ada.student_number
    and e.academic_year = ada.academic_year
    and ada.region = 'Miami'
    and ada.rn_year = 1
where
    e.rn_year = 1
    and e.grade_level in (7, 8)
    and e.academic_year >= {{ var("current_academic_year") - 1 }}
