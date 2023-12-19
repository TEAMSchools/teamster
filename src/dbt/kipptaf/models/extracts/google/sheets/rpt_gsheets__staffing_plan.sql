SELECT DISTINCT

sm.academic_year,
sm.culture,
sm.flex,
sm.entity,
sm.grade_band,
sm.recruitment_group,
sm.adp_department,
sm.adp_job_title,
sm.display_name,

lc.clean_name as adp_location,
lc.Abbreviation as short_name,
NULL AS recruiter,
NULL AS teammate,
'Active' AS plan_status,
NULL AS staffing_status,
NULL AS status_detail,
NULL AS mid_year_hire,
NULL AS recruiting_notes,
NULL AS staffing_model_notes,
NULL as gutcheck,

UPPER(CONCAT(lc.Abbreviation,sp.unique_id)) AS staffing_model_id,
COALESCE(cc.name,lc.Clean_Name) as campus,
FROM `{{ ref('stg_people__location_crosswalk') }}  AS lc
LEFT JOIN {{ ref('stg_people__staffing_model') }} as sm
on (lc.grade_band = sm.grade_band and lc.Region = sm.entity)
LEFT JOIN {{ ref('stg_people__campus_crosswalk') }} as cc
on (lc.PowerSchool_School_ID = cc.PowerSchool_School_ID)
where lc.Abbreviation is not null and lc.Abbreviation not in ('NCP','Truth','Sunrise','Liberty')
and sp.School <> 'All'

UNION ALL

/*HS have individual models, unioning on name instead of level and entity*/

SELECT DISTINCT

sp.academic_year,
sp.culture,
sp.flex,
sp.entity,
sp.grade_band,
sp.recruitment_group,
sp.adp_dept,
sp.adp_title,
sp.display_name,

lc.clean_name as adp_location,
lc.Abbreviation as short_name,
NULL AS recruiter,
NULL AS teammate,
'Active' AS plan_status,
NULL AS staffing_status,
NULL AS status_detail,
NULL AS mid_year_hire,
NULL AS recruiting_notes,
NULL AS staffing_model_notes,
NULL as gutcheck,

UPPER(CONCAT(lc.Abbreviation,sp.unique_id)) AS staffing_model_id,
COALESCE(cc.name,lc.Clean_Name) as campus,
FROM `teamster-332318.kipptaf_people.stg_people__location_crosswalk`  AS LC
LEFT JOIN `teamster-332318.cbaldor.src_gsheets_staffing_plan` as sp
on LC.Abbreviation = sp.school
LEFT JOIN `teamster-332318.kipptaf_people.stg_people__campus_crosswalk` as cc
on lc.PowerSchool_School_ID = cc.PowerSchool_School_ID
where lc.abbreviation is not null and lc.abbreviation not in ('NCP','Truth','Sunrise','Liberty')