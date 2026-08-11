with
    -- The upstream student_number holds the PREFIXED Focus id, not the network
    -- student number, so it is unprefixed here with the same rule
    -- int_students__students applies to the student spine. ps_schoolid is the
    -- PowerSchool-aligned school id the upstream already resolved through the
    -- locations crosswalk -- Focus's own schoolid is a small internal integer
    -- with no relation to the network school number.
    --
    -- Every Focus year is admitted, back to AY2018. Focus dates a returning
    -- student's stint to the real first day of school where PowerSchool used a
    -- July 1 administrative rollover, so 1,421 of Miami's 8,776 historical
    -- stints carry a different entrydate than the archive did -- concentrated
    -- in AY2021 (304) and AY2025 (973). entrydate feeds student_enrollment_key,
    -- so those keys are recomposed rather than preserved. That is deliberate:
    -- Focus is the system of record, and the archive's dates are not worth
    -- keeping the archive branch alive for.
    focus_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            region,
            academic_year,
            exitdate,
            enroll_status,
            entrycode,
            exitcode,
            grade_level,
            rn_year,
            year_in_school,
            year_in_network,
            is_enrolled_oct01,
            is_enrolled_oct15,
            is_enrolled_mar15,
            dob,
            state,

            ps_schoolid as schoolid,
            startdate as entrydate,
            student_first_name as first_name,
            student_last_name as last_name,

            network_student_number as student_number,
        from {{ ref("int_focus__student_enrollments") }}
    ),

    -- Focus is Miami's system of record for enrollment, and carries the full
    -- history back to AY2018, so the frozen archive contributes no Miami rows
    -- at all -- including its alumni graduate placeholders (enroll_status 3
    -- with null entry/exit dates, one per academic year).
    powerschool_conformed as (
        select *,
        from {{ ref("int_powerschool__student_enrollment_union") }}
        where _dbt_source_project != 'kippmiami'
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
