with
    -- The upstream student_number column is misnamed: it holds the PREFIXED
    -- Focus id, not the network student number, so anyone joining on the column
    -- name gets zero matches with no error. Unprefix it with the same rule
    -- int_focus__students_conformed applies to the student spine.
    --
    -- _dbt_source_relation is deliberately NOT projected. The consuming union
    -- generates its own, and carrying both would collide on the column name.
    -- _dbt_source_project IS projected so the union can coalesce it through
    -- rather than re-deriving 'kipptaf' from this model's own relation name.
    identified as (
        select
            _dbt_source_project,
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

            -- Focus's own schoolid is its internal id (14, 15, 58...), not the
            -- network school number. ps_schoolid is the PowerSchool id the
            -- upstream already resolved through the locations crosswalk.
            ps_schoolid as schoolid,

            -- fteid is deliberately not projected. The network column is a
            -- PowerSchool numeric full-time-equivalency id, while the Focus
            -- column of the same name holds a Florida education identifier
            -- string (FL000007024992). Same name, different concept -- casting
            -- it fails outright, and safe_cast would null real data under a
            -- misleading heading. The union null-fills it for Miami instead.
            startdate as entrydate,
            student_first_name as first_name,
            student_last_name as last_name,

            cast(
                regexp_replace(cast(student_number as string), r'^8400', '') as int64
            ) as student_number,
        from {{ ref("int_focus__student_enrollments") }}
    )

select *,
from identified
