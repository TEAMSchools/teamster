with
    iready as (
        select
            dr.student_id,
            dr.start_date,
            dr.completion_date,
            dr.baseline_diagnostic_y_n_,
            dr.most_recent_diagnostic_y_n_,
            dr.overall_scale_score,
            dr.percentile,
            dr.overall_relative_placement,
            dr.rush_flag,
            dr.overall_scale_score
            dr.mid_on_grade_level_scale_score,
            dr.percent_progress_to_annual_typical_growth_,
            dr.percent_progress_to_annual_stretch_growth_,
            dr.diagnostic_gain,
            dr.annual_typical_growth_measure,
            dr.annual_stretch_growth_measure,
            left(dr.academic_year, 4) as academic_year,
            + dr.annual_typical_growth_measure as scale_plus_typical,
            dr.overall_scale_score
            + dr.annual_typical_growth_measure as scale_plus_stretch,
            case
                when dr._file like '%ela%'
                then 'Reading'
                when dr._file like '%math%'
                then 'Math'
            end as subject,
            case
                dr.overall_relative_placement
                when '3 or More Grade Levels Below'
                then 1
                when '2 Grade Levels Below'
                then 2
                when '1 Grade Level Below'
                then 3
                when 'Early On Grade Level'
                then 4
                when 'Mid or Above Grade Level'
                then 5
            end as orp_numerical,
            case
                when
                    dr.overall_relative_placement
                    in ('Early On Grade Level', 'Mid or Above Grade Level')
                then 'On or Above Grade Level'
                when dr.overall_relative_placement = '1 Grade Level Below'
                then dr.overall_relative_placement
                when
                    dr.overall_relative_placement
                    in ('2 Grade Levels Below', '3 or More Grade Levels Below')
                then 'Two or More Grade Levels Below'
            end as placement_3_level,

            co.region,
            co.school_abbreviation,
            co.grade_level,
            case
                when co.region in ('KCNA', 'TEAM')
                then 'NJSLA'
                when co.region = 'KMS'
                then 'FL'
            end as destination_system,

            right(rt.time_per_name, 1) as round_number,
            coalesce(rt.alt_name, 'Outside Round') as test_round,

            case
                when rt.alt_name = 'BOY'
                then 'Fall ' + left(dr.academic_year, 4)
                when rt.alt_name = 'MOY'
                then 'Winter ' + right(dr.academic_year, 4)
                when rt.alt_name = 'EOY'
                then 'Spring ' + right(dr.academic_year, 4)
            end as test_round_date,

            count(*) over (
                partition by dr.student_id, dr.academic_year, dr._file, rt.alt_name
                order by dr.completion_date desc
            ) as rn_subj_round,

            count(*) over (
                partition by dr.student_id, dr.academic_year, dr._file
                order by dr.completion_date desc
            ) as rn_subj_year,
        from gabby.iready.diagnostic_results as dr
        inner join
            gabby.powerschool.cohort_identifiers_static as co
            on co.academic_year = left(dr.academic_year, 4)
            and co.student_number = dr.student_id
            and co.rn_year = 1
        left join
            gabby.reporting.reporting_terms as rt
            on dr.completion_date between rt.start_date and rt.end_date
            and rt.identifier = 'IR'
            and sc.region = rt.region
    )

select
    ir.academic_year,
    ir.student_id,
    ir.region,
    ir.school_abbreviation,
    ir.grade_level,
    ir.subject,
    ir.start_date,
    ir.completion_date,
    ir.round_number,
    ir.test_round,
    ir.test_round_date,
    ir.baseline_diagnostic_y_n_,
    ir.most_recent_diagnostic_y_n_,
    ir.overall_scale_score,
    ir.percentile,
    ir.overall_relative_placement,
    ir.orp_numerical,
    ir.placement_3_level,
    ir.rush_flag,
    ir.mid_on_grade_level_scale_score,
    ir.percent_progress_to_annual_typical_growth_,
    ir.percent_progress_to_annual_stretch_growth_,
    ir.diagnostic_gain,
    ir.annual_typical_growth_measure,
    ir.annual_stretch_growth_measure,
    ir.rn_subj_round,
    ir.rn_subj_year,

    cwo.sublevel_name as sa_proj_lvl,
    cwo.sublevel_number as sa_proj_lvl_num,

    cwt.sublevel_name as sa_proj_lvl_typ,
    cwt.sublevel_number as sa_proj_lvl_typ_num,
    cwt.sublevel_name as sa_proj_lvl_str,
    cwt.sublevel_number as sa_proj_lvl_str_num,
from iready as ir
left join
    gabby.assessments.fsa_iready_crosswalk as cwo
    on ir.overall_scale_score between cwo.scale_low and cwo.scale_high
    and ir.subject = cwo.test_name
    and ir.grade_level = cwo.grade_level
    and ir.destination_system = cwo.destination_system
    and cwo.source_system = 'i-Ready'
left join
    gabby.assessments.fsa_iready_crosswalk as cwt
    on ir.scale_plus_typical between cwt.scale_low and cwt.scale_high
    and ir.subject = cwt.test_name
    and ir.grade_level = cwt.grade_level
    and ir.destination_system = cwt.destination_system
    and cwt.source_system = 'i-Ready'
left join
    gabby.assessments.fsa_iready_crosswalk as cws
    on ir.scale_plus_stretch between cws.scale_low and cws.scale_high
    and ir.subject = cws.test_name
    and ir.grade_level = cws.grade_level
    and ir.destination_system = cws.destination_system
    and cws.source_system = 'i-Ready'
