with
    student_enrollments as (
        select
            _dbt_source_project,
            student_number,
            schoolid,
            academic_year,
            entrydate,
            exitdate,
        from {{ ref("int_students__student_enrollment_union") }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    enrollment_overlap as (
        select
            cc._dbt_source_project,
            cc.cc_dcid,
            cc.sections_dcid,
            cc.cc_academic_year,
            cc.cc_dateenrolled,
            cc.cc_dateleft,
            cc.is_dropped_section,
            cc.is_dropped_course,
            cc.cc_course_number,
            cc.teachernumber,
            cc.is_homeroom,

            enr._dbt_source_project as enr_source_project,
            enr.student_number as enr_student_number,
            enr.academic_year as enr_academic_year,
            enr.entrydate as enr_entrydate,

            (
                cc.cc_dateenrolled >= enr.entrydate
                and cc.cc_dateenrolled < enr.exitdate
            ) as is_covering,
        from {{ ref("int_students__course_enrollments") }} as cc
        -- alumni placeholder rows (enroll_status=3) have NULL entrydate/exitdate
        -- and match no stint here, producing a NULL student_enrollment_key
        --
        -- Focus leaves a course period's end_date null while the schedule is
        -- still open (PowerSchool always populates cc_dateleft), so the
        -- coalesce below is required for Miami to match its current stint.
        -- It is a no-op for NJ: cc_dateleft is null on zero NJ rows. entrydate
        -- and exitdate are never null in student_enrollments, so they need no
        -- equivalent coalesce. The ~10.6% of Miami rows still unmatched after
        -- this is an accepted residual within the NJ completed-year orphan-rate
        -- norm -- see the rate test in
        -- tests/test_miami_section_enrollment_orphan_rate.sql.
        --
        -- That residual is attributed, not unexplained. Of the orphaned
        -- Miami AY2026 rows, 1,886 hold a stint at the same school and fail the
        -- overlap; re-measured 2026-08-27 they split three ways:
        -- * 1,332 -- the STINT window is degenerate, with an exitdate on or
        -- before its entrydate. Nothing can overlap a window of zero or
        -- negative length, so no schedule date would fix these (#5024).
        -- * 478 -- the schedule row was closed on or before the stint's
        -- entrydate, so the student never attended the section.
        -- * 76 -- a future-term row (Semester 2, Quarter 2) for a student who
        -- already exited. cc_dateenrolled is the term start, so it lands
        -- after the exit by design (#5002).
        -- Zero rows have cc_dateenrolled before the stint's entrydate, which
        -- rules out the mid-term-joiner mechanism #4970 proposed.
        --
        -- The rest sit at a different campus: stale schedule rows left open
        -- after a reassignment, and courses taken at a second campus where
        -- int_focus__student_enrollment keeps only the primary stint (#5003).
        -- The Focus school-to-network mapping was ruled out for both.
        --
        -- All three stay null deliberately: attaching a section at one campus
        -- to the student's stint at another would emit a confidently wrong
        -- key, which is worse than no key (#4970).
        left join
            student_enrollments as enr
            on cc.students_student_number = enr.student_number
            and cc.sections_schoolid = enr.schoolid
            and cc.cc_academic_year = enr.academic_year
            and cc._dbt_source_project = enr._dbt_source_project
            and coalesce(cc.cc_dateleft, cast('9999-12-31' as date)) > enr.entrydate
            and cc.cc_dateenrolled < enr.exitdate
    ),

    enrollment_resolved as (
        {{
            dbt_utils.deduplicate(
                relation="enrollment_overlap",
                partition_by="cc_dcid, _dbt_source_project",
                order_by="is_covering desc, enr_entrydate asc",
            )
        }}
    ),

    section_enrollments as (
        select
            _dbt_source_project,
            cc_academic_year as academic_year,
            cc_dateenrolled as entry_date,
            cc_dateleft as exit_date,
            is_dropped_section,
            is_dropped_course,
            is_homeroom,
            cc_course_number,
            teachernumber,
            enr_source_project,
            enr_student_number,

            {{ dbt_utils.generate_surrogate_key(["cc_dcid", "_dbt_source_project"]) }}
            as student_section_enrollment_key,

            {{
                dbt_utils.generate_surrogate_key(
                    ["sections_dcid", "_dbt_source_project"]
                )
            }} as course_section_key,

            if(
                enr_student_number is not null,
                {{
                    dbt_utils.generate_surrogate_key(
                        [
                            "enr_student_number",
                            "enr_source_project",
                            "enr_academic_year",
                            "enr_entrydate",
                        ]
                    )
                }},
                cast(null as string)
            ) as student_enrollment_key,
        from enrollment_resolved
    ),

    section_enrollments_resolved as (
        select
            se.academic_year,
            se.entry_date,
            se.exit_date,
            se.is_dropped_section,
            se.is_dropped_course,
            se.is_homeroom,
            se.student_section_enrollment_key,
            se.course_section_key,
            se.student_enrollment_key,

            if(
                sr.employee_number is not null,
                {{ dbt_utils.generate_surrogate_key(["sr.employee_number"]) }},
                cast(null as string)
            ) as lead_teacher_staff_key,

            row_number() over (
                partition by
                    se._dbt_source_project,
                    se.enr_student_number,
                    se.enr_source_project,
                    se.academic_year,
                    se.cc_course_number
                order by
                    (se.is_dropped_section or se.is_dropped_course) asc,
                    coalesce(se.exit_date, cast('9999-12-31' as date)) desc,
                    se.entry_date desc,
                    se.student_section_enrollment_key asc
            ) as course_enrollment_rank,

            -- The current homeroom section per stint: rank homeroom rows within
            -- the enrollment stint and keep the most recent, so at most one
            -- current homeroom exists per stint even when a student carries
            -- concurrent HR sections (a data-quality case; deduped to latest).
            --
            -- _dbt_source_project is included because student_enrollment_key
            -- is NULL on every stint-orphaned row network-wide -- without it,
            -- every orphaned homeroom row, in any region, shares one
            -- partition and regions compete with each other for rank = 1.
            -- _dbt_source_project is non-null on every row, so adding it only
            -- tightens the partition.
            --
            -- The original reason was sharper: Miami's drop flags were null,
            -- and BigQuery sorts NULL FIRST under asc, so a Miami orphan
            -- outranked an NJ orphan on the leading term. #4968 made both
            -- flags non-null in every region, so that specific hazard is gone.
            -- The partition key stays regardless -- cross-region competition
            -- for one rank is wrong on its own.
            row_number() over (
                partition by
                    se._dbt_source_project, se.student_enrollment_key, se.is_homeroom
                order by
                    (se.is_dropped_section or se.is_dropped_course) asc,
                    coalesce(se.exit_date, cast('9999-12-31' as date)) desc,
                    se.entry_date desc,
                    se.student_section_enrollment_key asc
            ) as homeroom_rank,
        from section_enrollments as se
        left join
            {{ ref("int_people__staff_roster") }} as sr
            on se.teachernumber = sr.powerschool_teacher_number
    )

select
    academic_year,
    entry_date,
    exit_date,
    is_dropped_section,
    is_dropped_course,
    is_homeroom,
    student_section_enrollment_key,
    course_section_key,
    student_enrollment_key,
    lead_teacher_staff_key,

    (course_enrollment_rank = 1) as is_current_section_enrollment,
    (is_homeroom and homeroom_rank = 1) as is_current_homeroom,
from section_enrollments_resolved
