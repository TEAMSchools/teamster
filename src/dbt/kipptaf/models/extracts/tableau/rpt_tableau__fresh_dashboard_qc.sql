with
    fs_vs_ps_record_match as (
        select
            f.enrollment_academic_year,
            f.finalsite_enrollment_id,

            f.enrollment_type,

            'FS vs PS' as flag_type,
            'Enrollment Mismatch' as flag_name,
            'Enrollment record exists on FS but not PS' as flag_description,

            if(e.infosnap_id is null, true, false) as flag_value,

        from {{ ref("int_students__finalsite_student_roster") }} as f
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on f.enrollment_academic_year - 1 = e.academic_year
            and f.finalsite_enrollment_id = e.infosnap_id
            and e.rn_year = 1
        /* hardcoded year because finalsite academic years do not sync with ps
           academic years during review time */
        where f.enrollment_academic_year = 2026

        union all

        select
            e.academic_year,
            e.infosnap_id,

            f.enrollment_type,

            'PS vs FS' as flag_type,
            'Enrollment Mismatch' as flag_name,
            'Enrollment record exists on PS but not FS' as flag_description,

            if(f.finalsite_enrollment_id is null, true, false) as flag_value,

        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            {{ ref("int_students__finalsite_student_roster") }} as f
            on e.academic_year + 1 = f.enrollment_academic_year
            and e.infosnap_id = f.finalsite_enrollment_id
        /* hardcoded year because finalsite academic years do not sync with ps
           academic years during review time */
        where f.enrollment_academic_year = 2026
    )

select *,

from fs_vs_ps_record_match
where flag_value
