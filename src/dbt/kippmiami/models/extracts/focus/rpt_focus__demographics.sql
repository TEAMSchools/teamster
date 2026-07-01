with
    -- import once: send a student's demographics only if the student is not yet
    -- in Focus. Existing Focus demographics are never overwritten.
    focus_students as (
        select distinct cast(student_id as string) as student_id,
        from {{ ref("stg_focus__students") }}
    ),

    diffed as (
        select d.*,
        from {{ source("kipptaf_extracts", "rpt_focus__demographics") }} as d
        left join focus_students as f on d.stdt_id = f.student_id
        where f.student_id is null
    )

select
    stdt_id,
    last_name,
    first_name,
    name_suffix,
    middle_name,
    nickname,
    dt_birth,
    gender,
    lang,
    stdt_email,
    ethnic_hl,
    single_ethnic,
    race_am_ind_ak_nat,
    race_asian,
    race_black,
    race_nat_haw_pac_isl,
    race_white,
    residence_county,
    contry_birth,
    homeroom_tchr,
    resident_st,
    birth_loc,
    bdate_verif,
    immun_st,
    primary_home_lang,
    native_parent_lang,
    grde_enter_dist,
    msix_id,
    homeroom,
    pmrn,
    internt_perm,
    act_perm,
    direct_perm,
    screen_perm,
    photo_vid_perm,
    survey_perm,
    mckay_sch_attend,
    fhsaa_el3_ind,
    fhsaa_el3ch_ind,
    dt_home_lang_survey,
    casas_track,
    lcp_cont_stdt,
from diffed
