select
    b.*,

    a.category_code as assignment_category_code,
    a.category_name as assignment_category_name,
    a.name as assignment_name,
    a.duedate as due_date,
    a.scoretype as score_type,
    a.totalpointvalue as max_score,

    a.whocreated as created_by,
    a.whencreated as create_date,
    a.whomodified as modified_by,
    a.whenmodified as modify_date,

    a.publisheddate as published_date,
    a.transaction_date as date_ps_detected_updates,

    if(a.iscountedinfinalgrade = 1, true, false) as is_counted_final_grade,

from {{ ref("int_tableau__gradebook_audit_section_week_scaffold") }} as b
inner join
    {{ ref("int_powerschool__gradebook_assignments") }} as a
    on b.sections_dcid = a.sectionsdcid
    and a.duedate between b.week_start_monday and b.week_end_sunday
    and {{ union_dataset_join_clause(left_alias="b", right_alias="a") }}
where b.region_school_level not in ('CamdenES', 'NewarkES')
