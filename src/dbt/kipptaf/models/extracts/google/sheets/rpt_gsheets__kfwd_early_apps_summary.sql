with
    flagged_seniors as (
        select
            _dbt_source_project,
            overgrad_student_id,
            gpa_band,
            latest_overgrad_updated_at,
            school_key,
        from {{ ref("int_students__early_applications_rollup") }}
        where is_ed_ea_flagged
    ),

    seniors_by_school as (
        select _dbt_source_project, overgrad_student_id, gpa_band, school_key,
        from flagged_seniors

        union all

        select
            _dbt_source_project,
            overgrad_student_id,
            gpa_band,

            'all_schools' as school_key,
        from flagged_seniors
    ),

    senior_metrics as (
        select
            _dbt_source_project,
            overgrad_student_id,
            criterion_code as metric_code,
            is_met,
        from {{ ref("int_students__early_application_criteria_scaffold") }}

        union all

        select
            _dbt_source_project,
            overgrad_student_id,

            'met_both' as metric_code,

            logical_and(is_met) as is_met,
        from {{ ref("int_students__early_application_criteria_scaffold") }}
        group by _dbt_source_project, overgrad_student_id
    ),

    schools as (
        select school_key,
        from
            unnest(
                ['cooper_norcross', 'newark_collegiate', 'newark_lab', 'all_schools']
            ) as school_key
    ),

    bands as (
        select gpa_band, band_sort, count(*) as goal_count,
        from {{ ref("int_students__early_application_criteria") }}
        group by gpa_band, band_sort
    ),

    metrics as (
        select
            gpa_band,
            band_sort,

            criterion_code as metric_code,
            criterion_label as metric_label,
            criterion_sort as within_band_sort,
        from {{ ref("int_students__early_application_criteria") }}

        union all

        -- a band with more than 1 goal also gets a "met both" row, after its goals
        select
            gpa_band,
            band_sort,

            'met_both' as metric_code,
            'Met both' as metric_label,
            99 as within_band_sort,
        from bands
        where goal_count > 1
    ),

    metrics_sorted as (
        select
            metric_code,
            gpa_band,
            metric_label,

            row_number() over (order by band_sort, within_band_sort) as metric_sort,
        from metrics
    ),

    summary_groups as (
        select
            summary_group,

            array_agg(gpa_band) as band_filter,

            row_number() over (order by summary_sort) as group_sort,
        from {{ ref("int_students__early_application_gpa_bands") }}
        group by summary_group, summary_sort
    ),

    count_rows as (
        select
            1 as row_sort,
            'All' as gpa_band,
            'N: flagged Is ED/EA = Yes' as row_label,
            cast(null as string) as metric_code,
            'count' as basis,

            array_agg(gpa_band) as band_filter,
        from {{ ref("int_students__early_application_gpa_bands") }}

        union all

        -- 1 "Seniors in band" row per summary group, after the N row
        select
            1 + group_sort as row_sort,
            summary_group as gpa_band,
            'Seniors in band' as row_label,
            cast(null as string) as metric_code,
            'count' as basis,
            band_filter,
        from summary_groups
    ),

    last_count_row as (select max(row_sort) as last_row_sort, from count_rows),

    summary_rows as (
        select row_sort, gpa_band, row_label, metric_code, basis, band_filter,
        from count_rows

        union all

        -- after the count rows, each goal gets a "% of N" then a "% of band" row
        select
            l.last_row_sort + 2 * m.metric_sort - 1 as row_sort,
            m.gpa_band,
            m.metric_label || ': % of N' as row_label,
            m.metric_code,

            'n' as basis,

            [m.gpa_band] as band_filter,
        from metrics_sorted as m
        cross join last_count_row as l

        union all

        select
            l.last_row_sort + 2 * m.metric_sort as row_sort,
            m.gpa_band,
            m.metric_label || ': % of band' as row_label,
            m.metric_code,

            'band' as basis,

            [m.gpa_band] as band_filter,
        from metrics_sorted as m
        cross join last_count_row as l
    ),

    grid_seniors as (
        select
            r.row_sort,
            r.basis,

            s.school_key,

            sm.is_met,

            if(sb.overgrad_student_id is not null, true, false) as has_senior,
            if(sb.gpa_band in unnest(r.band_filter), true, false) as is_in_band,
        from summary_rows as r
        cross join schools as s
        left join seniors_by_school as sb on s.school_key = sb.school_key
        left join
            senior_metrics as sm
            on sb.overgrad_student_id = sm.overgrad_student_id
            and sb._dbt_source_project = sm._dbt_source_project
            and r.metric_code = sm.metric_code
    ),

    row_counts as (
        select
            row_sort,
            school_key,
            basis,

            countif(is_in_band and (basis = 'count' or is_met)) as met,
            countif(
                has_senior and (basis = 'n' or (basis = 'band' and is_in_band))
            ) as denominator_all,
        from grid_seniors
        group by row_sort, school_key, basis
    ),

    row_values as (
        select
            row_sort,
            school_key,
            basis,
            met,

            if(basis = 'count', null, denominator_all) as denominator,
            if(basis = 'count', null, safe_divide(met, denominator_all)) as pct,
        from row_counts
    ),

    row_rounded as (
        select
            row_sort,
            school_key,
            basis,
            met,
            denominator,
            pct,

            cast(round(100 * pct) as int64) as pct_whole,
        from row_values
    ),

    row_display as (
        select
            row_sort,
            school_key,
            met,
            denominator,
            pct,

            case
                when basis = 'count'
                then cast(met as string)
                when denominator = 0
                then '-'
                else format('%d%% (%d/%d)', pct_whole, met, denominator)
            end as display_value,
        from row_rounded
    ),

    as_of as (
        select
            max(
                date(latest_overgrad_updated_at, '{{ var("local_timezone") }}')
            ) as data_as_of,
        from flagged_seniors
    )

select
    r.row_sort,
    r.gpa_band,
    r.row_label,

    a.data_as_of,

    max(if(d.school_key = 'cooper_norcross', d.display_value, null)) as cooper_norcross,
    max(
        if(d.school_key = 'newark_collegiate', d.display_value, null)
    ) as newark_collegiate,
    max(if(d.school_key = 'newark_lab', d.display_value, null)) as newark_lab,
    max(if(d.school_key = 'all_schools', d.display_value, null)) as all_schools,

    max(if(d.school_key = 'cooper_norcross', d.met, null)) as cooper_norcross_met,
    max(
        if(d.school_key = 'cooper_norcross', d.denominator, null)
    ) as cooper_norcross_denominator,
    max(if(d.school_key = 'cooper_norcross', d.pct, null)) as cooper_norcross_pct,
    max(if(d.school_key = 'newark_collegiate', d.met, null)) as newark_collegiate_met,
    max(
        if(d.school_key = 'newark_collegiate', d.denominator, null)
    ) as newark_collegiate_denominator,
    max(if(d.school_key = 'newark_collegiate', d.pct, null)) as newark_collegiate_pct,
    max(if(d.school_key = 'newark_lab', d.met, null)) as newark_lab_met,
    max(if(d.school_key = 'newark_lab', d.denominator, null)) as newark_lab_denominator,
    max(if(d.school_key = 'newark_lab', d.pct, null)) as newark_lab_pct,
    max(if(d.school_key = 'all_schools', d.met, null)) as all_schools_met,
    max(
        if(d.school_key = 'all_schools', d.denominator, null)
    ) as all_schools_denominator,
    max(if(d.school_key = 'all_schools', d.pct, null)) as all_schools_pct,
from summary_rows as r
inner join row_display as d on r.row_sort = d.row_sort
cross join as_of as a
group by r.row_sort, r.gpa_band, r.row_label, a.data_as_of
