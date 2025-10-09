with
    assessment_union as (
        /* State Tests */
        select
            localstudentidentifier as student_number,
            discipline,
            assessment_name,

            academic_year + 1 as academic_year_join,

            is_proficient,
        from {{ ref("int_pearson__all_assessments") }}
        where assessment_name = 'NJSLA'

        union all

        select
            s.student_number,

            f.discipline,

            'FAST PM3' as assessment_name,

            f.academic_year + 1 as academic_year_join,

            f.is_proficient,
        from {{ ref("int_fldoe__all_assessments") }} as f
        left join
            {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
            on f.student_id = suf.fleid
            and {{ union_dataset_join_clause(left_alias="f", right_alias="suf") }}
        left join
            {{ ref("stg_powerschool__students") }} as s
            on suf.studentsdcid = s.dcid
            and {{ union_dataset_join_clause(left_alias="suf", right_alias="s") }}
        where
            f.administration_window = 'PM3'
            and f.assessment_name = 'FAST'
            and f.scale_score is not null

        union all

        select
            s.student_number,

            f.discipline,

            'FAST PM1' as assessment_name,

            f.academic_year as academic_year_join,

            f.is_proficient,
        from {{ ref("int_fldoe__all_assessments") }} as f
        left join
            {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
            on f.student_id = suf.fleid
            and {{ union_dataset_join_clause(left_alias="f", right_alias="suf") }}
        left join
            {{ ref("stg_powerschool__students") }} as s
            on suf.studentsdcid = s.dcid
            and {{ union_dataset_join_clause(left_alias="suf", right_alias="s") }}
        where
            f.administration_window = 'PM1'
            and f.assessment_name = 'FAST'
            and f.scale_score is not null

        union all

        /* i-Ready */
        select
            student_id as student_number,
            discipline,

            'i-Ready BOY Projected Proficient With Typical' as assessment_name,
            academic_year_int as academic_year_join,
            projected_is_proficient_typical as is_proficient,
        from {{ ref("base_iready__diagnostic_results") }}
        where
            test_round = 'BOY'
            and rn_subj_round = 1
            and projected_sublevel_number_typical is not null

        union all

        select
            student_id as student_number,
            discipline,

            'i-Ready BOY Proficient With Typical' as assessment_name,

            academic_year_int as academic_year_join,
            is_proficient_with_typical as is_proficient,
        from {{ ref("base_iready__diagnostic_results") }}
        where
            test_round = 'BOY'
            and rn_subj_round = 1
            and sublevel_number_with_typical is not null

        union all

        /* Star */
        select
            student_display_id as student_number,
            star_discipline as discipline,

            'Star EOY' as assessment_name,

            academic_year + 1 as academic_year_join,

            case
                when grade_level > 0 and state_benchmark_proficient = 'Yes'
                then true
                when grade_level > 0 and state_benchmark_proficient = 'No'
                then false
                when grade_level = 0 and district_benchmark_proficient = 'Yes'
                then true
                when grade_level = 0 and district_benchmark_proficient = 'No'
                then false
            end as is_proficient,
        from {{ ref("int_renlearn__star_rollup") }}
        where rn_subj_round = 1 and screening_period_window_name = 'Spring'

        union all

        select
            student_display_id as student_number,
            star_discipline as discipline,

            'Star BOY' as assessment_name,

            academic_year as academic_year_join,

            case
                when grade_level > 0 and state_benchmark_proficient = 'Yes'
                then true
                when grade_level > 0 and state_benchmark_proficient = 'No'
                then false
                when grade_level = 0 and district_benchmark_proficient = 'Yes'
                then true
                when grade_level = 0 and district_benchmark_proficient = 'No'
                then false
            end as is_proficient,
        from {{ ref("int_renlearn__star_rollup") }}
        where rn_subj_round = 1 and screening_period_window_name = 'Fall'
    )

select
    co.student_number,
    co.academic_year,
    co.grade_level,
    co.region,
    co.discipline,

    au.assessment_name,
    au.is_proficient,
from {{ ref("int_extracts__student_enrollments_subjects") }} as co
left join
    assessment_union as au
    on co.academic_year = au.academic_year_join
    and co.student_number = au.student_number
    and co.discipline = au.discipline
where co.rn_year = 1
