with
    scaffold as (
        select
            b.academic_year,,
            b.org,
            b.region,
            b.schoolid,
            b.school,
            b.grade_level,

            metric,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as b
        cross join
            unnest(
                [
                    'Applications',
                    'Offers',
                    'Pending Offers',
                    'Pending Offer <= 4',
                    'Pending Offer >= 5 & <=10',
                    'Pending Offer > 10',
                    'Conversion'
                ]
            ) as metric
    )

select *,
from scaffold
