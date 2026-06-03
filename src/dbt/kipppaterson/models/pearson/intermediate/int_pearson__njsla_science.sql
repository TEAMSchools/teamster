-- Pearson reports the KIPP student_number directly as LocalStudentIdentifier
-- for Paterson (#4103), so no district-id translation is needed. Retained as a
-- pass-through because kipptaf sources Paterson Pearson from this intermediate.
select *, from {{ ref("stg_pearson__njsla_science") }}
