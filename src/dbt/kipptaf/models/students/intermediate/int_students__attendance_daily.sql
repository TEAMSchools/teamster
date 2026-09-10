with
    -- Focus's school_id is its internal id (14, 15, 58...), not the network
    -- school number. The inner join is also the filter that drops Focus's
    -- non-instructional schools, which have no locations row.
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    -- Focus re-dated Miami's enrollment stints (a returning student's stint
    -- starts on the real first day of school, where PowerSchool used a July 1
    -- rollover), and entrydate feeds student_enrollment_key, so the frozen
    -- archive's Miami rows are re-keyed to the Focus stint that contains the
    -- day (#4803, #5114). Only Miami stints: NJ attendance already agrees with
    -- its enrollment source.
    focus_stints as (
        select student_number, entrydate, exitdate, academic_year - 1990 as yearid,
        from {{ ref("int_students__student_enrollment_union") }}
        where _dbt_source_project = 'kippmiami'
    ),

    -- The frozen PowerSchool archive ends at AY2025 (rebuilt with that bound,
    -- #5012), so every archive row is a pre-Focus year and needs no cutover
    -- predicate. The Focus branch below still floors at the cutover year.
    powerschool_conformed as (
        select
            ps.* except (entrydate),

            -- PowerSchool has no analog to Focus's "register never taken"
            -- signal. Every PowerSchool row IS a recorded attendance row,
            -- because PowerSchool records only absences and implies presence.
            -- False, not null: this column must never be null network-wide
            -- (see the model's grain/null-scaffold test), and null here would
            -- read as "unknown" when it actually means "not the Focus
            -- recorded-register concept".
            false as is_attendance_recorded,

            -- Explicit, system-agnostic discriminator for the calcs CTE's
            -- #4927 null-outs below -- NOT derived from studentid or any other
            -- PowerSchool-specific column, so it survives PowerSchool
            -- compatibility scaffolding (studentid included) eventually
            -- leaving this model.
            false as is_focus_source,

            -- Archive date when no Focus stint contains the day (51 AY2025 rows
            -- per #4803); those rows already resolve on the archive date.
            coalesce(fs.entrydate, ps.entrydate) as entrydate,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as ps
        -- Half-open: the union conforms exitdate to the day after the stint's
        -- last day, and the roster trims each stint to the day before the next
        -- starts, so one day matches at most one stint.
        left join
            focus_stints as fs
            on ps.student_number = fs.student_number
            and ps.yearid = fs.yearid
            and ps.calendardate >= fs.entrydate
            and ps.calendardate < fs.exitdate
    ),

    -- The whole Focus-to-network translation lives here. See "The conform
    -- contract" above. A `select *` will NOT work: the Focus model shares no
    -- column names with the PowerSchool branch any more.
    focus_conformed as (
        select
            ad.student_number,
            ad.grade_level,
            ad.is_attendance_recorded,
            ad.startdate as entrydate,
            ad.school_date as calendardate,

            -- Carried through explicitly. Every downstream join keys on
            -- `_dbt_source_project`, and `student_enrollment_key` hashes it,
            -- so null-filling it through `full union all corresponding` breaks
            -- the Miami joins and mis-hashes the key. The kipptaf passthrough
            -- wrapper supplies both: `union_relations` adds
            -- `_dbt_source_relation`, and `extract_source_project` adds
            -- `_dbt_source_project`.
            ad._dbt_source_relation,
            ad._dbt_source_project,

            fs.schoolid,

            fcw.week_start_monday,
            fcw.week_end_sunday,
            fcw.week_number_academic_year,

            -- See powerschool_conformed's is_focus_source for why this is an
            -- explicit flag rather than a studentid-null proxy.
            true as is_focus_source,

            cast(ad.state_value as float64) as attendancevalue,

            -- Every row of int_focus__attendance_daily IS an in-session
            -- membership day, so these are constants here rather than
            -- sourced values.
            cast(1 as float64) as membershipvalue,
            cast(1 as float64) as potential_attendancevalue,

            -- PowerSchool-only machinery Focus cannot supply. Typed so the
            -- union binds; see the conform contract for why each one is
            -- unknowable.
            cast(null as int64) as studentid,
            cast(null as int64) as fteid,
            cast(null as int64) as attendance_conversion_id,
            cast(null as int64) as ontrack,
            cast(null as int64) as offtrack,
            cast(null as string) as student_track,

            ad.academic_year - 1990 as yearid,

            -- U means an unexcused absence in Focus and "Unprepared" in
            -- PowerSchool, so it MUST be remapped. AE and AD already mean the
            -- same thing in both systems and pass through. A present or
            -- unrecorded day leaves daily_code null, which is exactly how
            -- PowerSchool encodes it.
            if(ad.daily_code = 'U', 'A', ad.daily_code) as att_code,
        from {{ ref("int_focus__attendance_daily") }} as ad
        inner join focus_schools as fs on ad.schoolid = fs.focus_school_id
        left join
            {{ ref("int_focus__calendar_week") }} as fcw
            on ad.schoolid = fcw.schoolid
            and ad.academic_year = fcw.academic_year
            and ad.school_date between fcw.week_start_monday and fcw.week_end_sunday
            and ad._dbt_source_project = fcw._dbt_source_project
        -- One row. See int_students__sis_cutover for why the boundary is a
        -- floor derived from recorded attendance rather than from Focus row
        -- presence: int_focus__attendance_daily scaffolds a present-by-default
        -- row back to AY2020, so scoping on the years it contains would
        -- replace six years of real PowerSchool attendance with fabricated
        -- perfect attendance. Required, not belt-and-braces: without it
        -- Focus's AY2020 through AY2025 rows land beside PowerSchool's real
        -- rows for the same Miami school-days and break this model's own
        -- grain test.
        cross join {{ ref("int_students__sis_cutover") }} as c
        where ad.academic_year >= c.focus_start_academic_year
    ),

    -- `full union all corresponding` matches columns by NAME. A plain
    -- `union all` matches by POSITION, and the two CTEs above list schoolid
    -- in different positions, which would silently misalign columns.
    memberships as (
        select *,
        from powerschool_conformed

        full union all corresponding

        select *,
        from focus_conformed
    ),

    calcs as (
        select
            mem._dbt_source_relation,
            mem._dbt_source_project,
            mem.studentid,
            mem.student_number,
            mem.schoolid,
            mem.entrydate,
            mem.calendardate,
            mem.fteid,
            mem.attendance_conversion_id,
            mem.grade_level,
            mem.ontrack,
            mem.offtrack,
            mem.student_track,
            mem.yearid,
            mem.att_code,
            mem.is_attendance_recorded,
            mem.attendancevalue,
            mem.potential_attendancevalue,
            mem.membershipvalue,
            mem.week_start_monday,
            mem.week_end_sunday,
            mem.week_number_academic_year,

            t.academic_year,
            t.semester,
            t.term,

            abs(mem.attendancevalue - 1) as is_absent,

            -- TODO(#4927): Focus records tardies only at period grain, so
            -- is_tardy, is_ontime, and is_present_weighted's tardy weighting
            -- have no Miami source. Null rather than a fabricated 0 or 1 so
            -- Miami is excluded from network tardy metrics rather than
            -- reading as a verified zero. Discriminated on is_focus_source,
            -- not is_attendance_recorded -- that column is FALSE (never null)
            -- on BOTH the frozen Miami PowerSchool archive and Focus-sourced
            -- Miami rows, so it can't tell them apart.
            if(
                mem.is_focus_source, null, if(mem.att_code like 'T%', 1.0, 0.0)
            ) as is_tardy,
            if(
                mem.is_focus_source, null, if(mem.att_code like 'T%', 0.0, 1.0)
            ) as is_ontime,
            if(
                mem.att_code like 'T%', 0.67, mem.attendancevalue
            ) as is_present_weighted,

            -- TODO(#4927): Focus attendance carries no suspension codes at
            -- any grain. Miami suspension data lives in DeansList and is not
            -- sourced here. Null so a network suspension rate excludes Miami
            -- rather than diluting itself with false zeros.
            if(
                mem.is_focus_source,
                null,
                if(mem.att_code in ('OS', 'OSS', 'OSSP', 'SHI'), 1.0, 0.0)
            ) as is_oss,
            if(
                mem.is_focus_source, null, if(mem.att_code in ('S', 'ISS'), 1.0, 0.0)
            ) as is_iss,
            if(
                mem.is_focus_source,
                null,
                if(mem.att_code in ('OS', 'OSS', 'OSSP', 'S', 'ISS', 'SHI'), 1.0, 0.0)
            ) as is_suspended,
            if(
                mem.is_focus_source,
                null,
                if(
                    mem.att_code not in ('ISS', 'OSS', 'OS', 'OSSP', 'SHI'),
                    abs(mem.attendancevalue - 1),
                    0.0
                )
            ) as is_absent_non_susp,

            -- A day that has actually occurred (<= today). The
            -- `membership_reg` calendar join emits a row for every in-session
            -- day in the enrollment span, including future year-end days.
            -- Point-in-time anchors must ignore those days, or they latch onto
            -- the future last day of the year and collapse to zero once the
            -- fact filters to `calendardate` <= `current_date`.
            mem.calendardate
            <= current_date('{{ var("local_timezone") }}') as is_realized,

        from memberships as mem
        inner join
            {{ ref("int_students__terms") }} as t
            on mem.yearid = t.yearid
            and mem.schoolid = t.schoolid
            and mem.calendardate between t.term_start_date and t.term_end_date
            and mem._dbt_source_project = t._dbt_source_project
            and t.term is not null
        -- Membership days outside any calendar week have no week fields. The
        -- former inner join to calendar_week dropped them; this keeps the row
        -- set identical (#5193).
        where mem.week_start_monday is not null
    ),

    anchors as (
        select
            *,

            -- Per-school point-in-time enrollment anchors. Drive the
            -- student_enrollments Cube. Anchored on the latest *realized*
            -- (past or today) in-session day per school so the as-of-now
            -- headcount can't collapse onto a future year-end row the fact
            -- filters out.
            calendardate = max(if(is_realized, calendardate, null)) over (
                partition by schoolid, _dbt_source_project, academic_year
            ) as is_current_record,

            calendardate = max(if(is_realized, calendardate, null)) over (
                partition by
                    schoolid,
                    _dbt_source_project,
                    academic_year,
                    date_trunc(calendardate, month)
            ) as is_enrollment_month_end_record,

            calendardate = max(if(is_realized, calendardate, null)) over (
                partition by schoolid, _dbt_source_project, week_start_monday
            ) as is_enrollment_week_end_record,

            -- Per-stint attendance anchors. These drive the
            -- `student_attendance` Cube's latest, month-end and week-end CA
            -- snapshots. The stint is (`student_number`,
            -- `_dbt_source_project`, `academic_year`, `entrydate`), the
            -- natural key behind `student_enrollment_key` in the fact. Latest
            -- is the stint's last realized day; month-end and week-end are its
            -- last realized membership day in the period.
            calendardate = max(if(is_realized, calendardate, null)) over (
                partition by
                    student_number, _dbt_source_project, academic_year, entrydate
            ) as is_latest_record,

            (
                calendardate
                = max(
                    if(is_realized and membershipvalue = 1, calendardate, null)
                ) over (
                    partition by
                        student_number,
                        _dbt_source_project,
                        academic_year,
                        entrydate,
                        date_trunc(calendardate, month)
                )
                and membershipvalue = 1
            ) as is_month_end_record,

            (
                calendardate
                = max(
                    if(is_realized and membershipvalue = 1, calendardate, null)
                ) over (
                    partition by
                        student_number,
                        _dbt_source_project,
                        academic_year,
                        entrydate,
                        week_start_monday
                )
                and membershipvalue = 1
            ) as is_week_end_record,

        from calcs
    ),

    running_calcs as (
        select
            *,

            sum(is_absent) over (
                partition by student_number, academic_year
                order by calendardate asc
                rows between 90 preceding and current row
            ) as n_absent_running_90,

            avg(is_absent) over (
                partition by academic_year, student_number order by calendardate asc
            ) as pct_absent_running_student_year,

            sum(membershipvalue) over (
                partition by academic_year, student_number
            ) as n_membership_student_year,

        from anchors
    )

select
    _dbt_source_relation,
    studentid,
    student_number,
    schoolid,
    entrydate,
    calendardate,
    fteid,
    attendance_conversion_id,
    grade_level,
    ontrack,
    offtrack,
    student_track,
    yearid,
    att_code,
    is_attendance_recorded,
    attendancevalue,
    potential_attendancevalue,
    membershipvalue,
    academic_year,
    semester,
    term,
    week_start_monday,
    week_end_sunday,
    week_number_academic_year,
    _dbt_source_project,
    is_absent,
    is_present_weighted,
    is_tardy,
    is_ontime,
    is_oss,
    is_iss,
    is_suspended,
    is_absent_non_susp,
    n_absent_running_90,
    pct_absent_running_student_year,
    n_membership_student_year,
    is_current_record,
    is_enrollment_month_end_record,
    is_enrollment_week_end_record,
    is_latest_record,
    is_month_end_record,
    is_week_end_record,

    -- Neutral names, exposed alongside the legacy PowerSchool-derived ones so
    -- consumers can migrate independently. The legacy set is transitional;
    -- see the properties yml.
    calendardate as school_date,
    entrydate as enrollment_start_date,
    att_code as attendance_code,
    attendancevalue as is_present,
    membershipvalue as is_in_membership,

    pct_absent_running_student_year * n_membership_student_year as n_absent_projected,
    yearid + 1990 as academic_year_neutral,

    case
        when _dbt_source_project = 'kippmiami' and n_absent_running_90 >= 15
        then true
        when
            _dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
            and pct_absent_running_student_year * n_membership_student_year >= 50
        then true
        else false
    end as is_truant,

from running_calcs
