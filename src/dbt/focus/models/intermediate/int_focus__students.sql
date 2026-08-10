-- Staging columns plus their decoded custom-field labels. Drives from staging
-- and LEFT JOINs the pivot: BigQuery UNPIVOT drops entities whose unpivoted
-- columns are all null, so the pivot alone is not a complete entity spine.
--
-- Also conforms the fields whose Focus representation differs from the network
-- one, so every consumer reads the same derivation rather than repeating it.
with
    labeled as (
        select
            s.*,

            p.ethnicity_hispanic_or_latino_label,
            p.race_white_label,
            p.race_black_or_african_american_label,
            p.race_asian_label,
            p.sex_label,
            p.race_american_indian_or_alaska_native_label,
            p.race_native_hawaiian_or_other_pacific_islander_label,
            p.residence_county_label,
            p.language_label,
            p.ese_fefp_code_label,
            p.english_language_learner_pk_12_label,
            p.gifted_eligibility_label,
        from {{ ref("stg_focus__students") }} as s
        left join
            {{ ref("int_focus__students__pivot") }} as p on s.student_id = p.student_id
    ),

    raced as (
        select
            *,

            (
                if(race_black_or_african_american_label = 'Yes', 1, 0)
                + if(race_white_label = 'Yes', 1, 0)
                + if(race_asian_label = 'Yes', 1, 0)
                + if(race_american_indian_or_alaska_native_label = 'Yes', 1, 0)
                + if(race_native_hawaiian_or_other_pacific_islander_label = 'Yes', 1, 0)
            ) as race_count,
        from labeled
    )

select
    *,

    -- student_id is the network student number prefixed with 8400,
    -- Miami-Dade's FLDOE district number. Strip it where present and pass any
    -- other value through unchanged, so the one known anomalous id stays
    -- visible instead of being silently mangled.
    cast(
        regexp_replace(cast(student_id as string), r'^8400', '') as int64
    ) as student_number,

    date(birthdate) as dob,

    regexp_extract(sex_label, r'\[(\w+)\]') as gender,

    -- The MDCPS student id, stored as NUMERIC, which drops the leading zero
    -- most of them carry. Pad back to the 7 digits MDCPS issues.
    lpad(cast(disis_id as string), 7, '0') as state_studentnumber,

    -- ESE FEFP Code is the only ESE field Focus stores. It is a funding-matrix
    -- code, so any value means the student receives ESE services; its absence
    -- does not mean the student has no IEP, hence null rather than 'No IEP'.
    if(ese_fefp_code_label is not null, 'SPED', null) as spedlep,

    -- Gifted Eligibility records the FLDOE criteria paragraph a student
    -- qualified under, so any A or B is gifted and Z is not.
    case
        when gifted_eligibility_label like 'Student was determined eligible%'
        then 'Y'
        when gifted_eligibility_label is not null
        then 'N'
    end as gifted_and_talented,

    -- FLDOE ELL codes. LY is currently LEP; the followup, exited and
    -- not-applicable codes are not. The tested-or-pending codes are left null
    -- because they are genuinely unknown rather than negative.
    case
        regexp_extract(english_language_learner_pk_12_label, r'\[(\w+)\]')
        when 'LY'
        then true
        when 'LF'
        then false
        when 'LA'
        then false
        when 'LZ'
        then false
        when 'TZ'
        then false
        when 'ZZ'
        then false
    end as lep_status,

    -- Single-character race code matching the network domain. Multiple races
    -- yield T, a single race yields its code, and no recorded race yields null
    -- rather than a fabricated category.
    case
        when race_count > 1
        then 'T'
        when race_black_or_african_american_label = 'Yes'
        then 'B'
        when race_white_label = 'Yes'
        then 'W'
        when race_asian_label = 'Yes'
        then 'A'
        when race_american_indian_or_alaska_native_label = 'Yes'
        then 'I'
        when race_native_hawaiian_or_other_pacific_islander_label = 'Yes'
        then 'P'
    end as ethnicity,
from raced
