{{ config(severity="warn") }}

-- A student with more parents than the two conventional slots. The wide
-- downstream receivers (contacts pivot, ParentSquare, DeansList, the contacts
-- bridge) all carry two parent columns, so anything past contact_2 is emitted
-- here but dropped before it reaches an extract. Warn so the count stays
-- visible; matching `contact_%` rather than a literal catches a fourth slot too.
select finalsite_enrollment_id, contact_slot,
from {{ ref("int_finalsite__student_contacts") }}
where contact_slot like 'contact\\_%' and contact_slot not in ('contact_1', 'contact_2')
