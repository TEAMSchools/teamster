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

        select
            student_id as student_number,
            discipline,

            'i-Ready BOY Proficient' as assessment_name,

            academic_year_int as academic_year_join,
            is_proficient,
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

        union all
        /* SAT/PSAT */
        select
            student_number,

            if(subject_area = 'EBRW', 'ELA', subject_area) as discipline,

            'PSAT' as assessment_name,

            academic_year + 1 as academic_year_join,
            case
                when subject_area = 'EBRW' and scale_score >= 430
                then true
                when subject_area = 'Math' and scale_score >= 480
                then true
                when subject_area = 'EBRW' and scale_score < 430
                then false
                when subject_area = 'Math' and scale_score < 480
                then false
            end as is_proficient,
        from {{ ref("int_assessments__college_assessment") }}
        where scope = 'PSAT NMSQT' and subject_area in ('EBRW', 'Math')
    ),

    assessment_pivot as (
        select
            academic_year_join,
            student_number,
            discipline,
            iready_projected_proficient_typical,
            star_boy,
            star_eoy,
            iready_proficient_typical,
            fast_pm1,
            fast_pm3,
            njsla,
            psat,
            iready_proficient,
        from
            assessment_union pivot (
                max(is_proficient) for assessment_name in (
                    'i-Ready BOY Projected Proficient With Typical'
                    as iready_projected_proficient_typical,
                    'Star BOY' as star_boy,
                    'Star EOY' as star_eoy,
                    'i-Ready BOY Proficient With Typical' as iready_proficient_typical,
                    'FAST PM1' as fast_pm1,
                    'FAST PM3' as fast_pm3,
                    'NJSLA' as njsla,
                    'PSAT' as psat,
                    'i-Ready BOY Proficient' as iready_proficient
                )
            )
    ),

    {# TODO: Date limiters#}
    bucket_programs as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            trim(split(specprog_name, '-')[offset(0)]) as bucket,
            trim(split(specprog_name, '-')[offset(1)]) as discipline,
        from {{ ref("int_powerschool__spenrollments") }}
        where specprog_name like 'Bucket%'
    )

select
    co.student_number,
    co.student_first_name,
    co.student_last_name,
    co.dob,
    co.entrydate,
    co.exitdate,
    co.academic_year,
    co.grade_level,
    co.region,
    co.discipline,

    case
        /* NJ */
        when
            co.region in ('Camden', 'Newark')
            and co.grade_level < 3
            and ap.iready_proficient_typical
        then 'Bucket 1'
        when
            co.region in ('Camden', 'Newark')
            and co.grade_level = 3
            and ap.iready_projected_proficient_typical
        then 'Bucket 1'
        when
            co.region in ('Camden', 'Newark')
            and co.grade_level < 9
            and coalesce(ap.njsla, ap.iready_projected_proficient_typical)
        then 'Bucket 1'
        when
            co.region in ('Camden', 'Newark')
            and co.grade_level = 9
            and coalesce(ap.njsla, ap.iready_proficient_typical)
        then 'Bucket 1'
        when co.region in ('Camden', 'Newark') and co.grade_level < 11 and psat
        then 'Bucket 1'
        when co.region in ('Camden', 'Newark') and co.grade_level = 11 and psat
        then 'Bucket 1'

        /* FL */
        when co.region = 'Miami' and co.grade_level = 0 and ap.star_boy
        then 'Bucket 1'
        when
            co.region = 'Miami'
            and co.grade_level < 3
            and coalesce(ap.star_eoy, ap.iready_proficient_typical)
        then 'Bucket 1'
        when
            co.region = 'Miami'
            and co.grade_level = 3
            and coalesce(ap.fast_pm1, ap.iready_projected_proficient_typical)
        then 'Bucket 1'
        when
            co.region = 'Miami'
            and co.grade_level <= 8
            and coalesce(ap.fast_pm3, ap.iready_projected_proficient_typical)
        then 'Bucket 1'

        /* PowerSchool Student Programs */
        when bp.bucket = 'Bucket 2'
        then bp.bucket
        when bp.bucket = 'Bucket 3'
        then bp.bucket
        else 'Bucket 4'
    end as bucket,
from {{ ref("int_extracts__student_enrollments_subjects") }} as co
left join
    assessment_pivot as ap
    on co.academic_year = ap.academic_year_join
    and co.student_number = ap.student_number
    and co.discipline = ap.discipline
left join
    bucket_programs as bp
    on co.studentid = bp.studentid
    and co.academic_year = bp.academic_year
    and co.discipline = bp.discipline
    and {{ union_dataset_join_clause(left_alias="co", right_alias="bp") }}
where
    co.rn_year = 1
    and co.grade_level between 0 and 11
    and co.academic_year = {{ var("current_academic_year") }}
