# CSGF Data Collection Field Definitions — Extracted Reference

Source: Google Sheet titled "Data Collection Field Definitions," owned by
`hmccoy@chartergrowthfund.org` (CSGF), shared with KTAF. This is CSGF's own
column-by-column definition of every field they ask charter networks to submit.
No student-level or personally identifying data lives in this file — it's
field/column definitions only (school- and org-level metadata), safe to quote
from directly.

Link:
[Data Collection Field Definitions](https://docs.google.com/spreadsheets/d/1hpMLqeFcci_Epar3InHRB8UXly7ZLg42vzjgANUpzP8/edit?gid=963005787#gid=963005787)

**Use this doc to resolve what a CSGF field means before entering data or
documenting a `rpt_gsheets__csgf_*` model's column mapping.** It is CSGF's own
source of truth for field semantics — prefer it over guessing from a field name
alone.

---

## 1. Schools List Field Definitions

Fields, in order: School Name; State School ID; NCES ID; Lowest/Highest Grade
Served 2025-26; School Model (+ 19-category sub-list); School Model Description;
Take over/Merger/Turnaround?; Date of Take over or Merger; Additional Contect
[sic]; Academic Year Opened; Academic Year Closed; Next Charter Renewal Date;
Authorizing District or Entity; Authorizing Entity Type; Public School District;
Street Address; City; State; Zip; Administers NWEA MAP?; Administers iReady?;
Facility Ownership Type; Lease Term Including Extensions; and three conditional
real-estate-financing questions.

Definitions worth getting exactly right:

- **State School ID**: displayed as `[district code]-[school code]` (e.g.
  `00-00000`) — no state abbreviation, follow the same convention for new codes.
- **NCES ID**: 12-digit numeric code from
  [nces.ed.gov/ccd/schoolsearch](https://nces.ed.gov/ccd/schoolsearch/).
- **Lowest/Highest Grade Served**: picklist `PK, K, 1–12`.
- **School Model**: multi-select picklist of 19 categories (Adult Education,
  Arts-Focused, Blended/Personalized, Career Exposure, Classical, College Prep,
  Diverse by Design, Dual Language, EL/Project-Based, Montessori, Opportunity
  Youth HS, Play-based Learning, SEL/Character, Special Populations, STEM/STEAM,
  Turnaround, Virtual, Waldorf, Other); "Other" requires a self-description in
  the next column.
- **Date of Take over or Merger**: format `MM/YYYY - MM/YYYY`.
- **Academic Year Opened / Closed**: format `YYYY-YYYY`; Closed only if
  applicable, otherwise blank.
- **Next Charter Renewal Date**: format `MM/DD/YYYY`.
- **Additional Contect** [sic — CSGF's typo, not ours]: conditional — only fill
  in if the school closed at the end of the prior year, or is a
  takeover/turnaround/merger.
- **Authorizing Entity Type**: fixed picklist — Local Education Agency, County
  Education Agency, State Education Agency, Independent Chartering Board, Higher
  Education Institution, Non-Educational Government Entity, Nonprofit
  Organization.
- **State**: 2-char abbreviation. **Zip**: 5 digits.
- **Facility Ownership Type**: picklist — District Lease, Government Lease,
  Private Lease, School Ownership, Lease with a purchase option.
- **Lease Term Including Extensions**: picklist — 0-9 years, 10+ years, or not
  applicable.
- The three real-estate-financing questions cascade conditionally off a
  "Yes"/"No" answer to the first.

## 2. Enrollment & School Information Field Definitions

(Note: CSGF's table of contents lists this as "Enrollment **and Annual** School
Information" — the actual section header drops "Annual." Use the header wording,
not the TOC wording, when citing this section by name.)

Fields, in order: School Name; Lowest/Highest Grade Served 2025-26
(pre-populated from Schools List); Total Instructional Days 2025-26; Total
Budgeted Enrollment 2025-26; Total Seat Capacity 2026-27; Total Seats When
Growth Plan Complete; 2025-26 Grade Level/Race-Ethnicity/Special Program
Enrollment; 2025-26 Students Qualifying for FRL or Direct Cert (New Schools
Only); Student Retention 2024-25→2025-26; 2024-25 Average Daily Attendance Rate;
2024-25 Chronic Absenteeism Rate; 2025-26 Teacher Counts; Teacher Retention
2024-25→2025-26; School Leader/Principal Demographics (two rows: primary leader
and co-leader, same field label for both).

Definitions worth getting exactly right:

- **Grade Level / Race-Ethnicity / Special Program Enrollment**: counted "on
  October 1, or your state's official 'count day.'" Race/ethnicity groups align
  with the federal CRDC (Civil Rights Data Collection) taxonomy. **Watch this
  one**: the field is named "2025-26" but its own description says the count
  date is "October 1... of the **2026-27** school year" — item name and
  description disagree on year in CSGF's source. Confirm the intended year
  directly with CSGF (or from the portal's live field help) before treating
  either as authoritative.
- **FRL or Direct Cert (New Schools Only)**: conditional — only for schools new
  in 2025-26; existing schools may leave blank (CSGF's Analytics team back-fills
  from public state reporting).
- **Student Retention**: denominator = enrollment on the fall-2024 state count
  day; numerator = still enrolled on the fall-2025 count day, plus students who
  completed the highest grade in spring 2025 (graduates count as retained).
- **Teacher Counts**: "Teacher" = anyone spending >50% of time on direct
  instruction; explicitly excludes aides/assistants/fellows.
- **Teacher Retention**: denominator = teachers employed any time 9/1/24–4/30/25
  (same >50%-instruction definition); numerator = still employed in any role on
  9/2/25.
- **Total Seat Capacity 2026-27**: CSGF's own doc gives two different
  definitions ("Option 1" / "Option 2") rather than settling on one — flag this
  to CSGF or pick one and document the choice rather than treating it as
  self-evident.

## 3. Discipline Data Field Definitions

Fields: School; Out-of-School Suspensions (# unique incidents) 2025-26;
In-School Suspensions (# unique incidents) 2025-26; Total # of Expulsions
2025-26; Cumulative Enrollment 2025-26; Total Count of Students Suspended At
Least Once / Multiple Times 2025-26; and the same three counts broken out by
Student Group.

Definitions worth getting exactly right:

- **OSS/ISS incident counts**: one incident = one disciplinary action resulting
  in that suspension type, regardless of days served. A student suspended twice
  = 2 incidents.
- **Expulsions**: permanent removal, as formally designated by the state or
  authorizer — not a long-term suspension or alternative placement, unless the
  state itself classifies it as an expulsion.
- **Cumulative Enrollment**: window is the state's count date through the last
  day of school; enter one school-wide total, with the by-group breakdown
  entered separately.
- **Suspended At Least Once / Multiple Times**: explicit dedup rule — count each
  student once regardless of suspension type/incident count; "multiple" = 2+
  incidents combining in-school and out-of-school.
- **Student Group breakdown rows**: the field descriptions state their own
  validation rule ("each group count must be < the Total Count," "the sum of
  race category counts must equal the Total Count," same for gender) — but they
  say "see list above" for the student-group categories, and **no such list
  actually appears in the Discipline section.** The real enumerated
  race/ethnicity and gender categories only exist in the Org Staffing Summary
  section below — cross-reference there.

## 4. Org Staffing Summary Field Definitions

Only 5 fields: Category; Total # Staff 2024-25; Total # Staff 2025-26; Counts by
Race/Ethnicity (2025-26 only — counts, not percentages); Counts by Gender
(same).

- **Category** (quote CSGF's own wording in full when citing): "Categories for
  School and Org Staff: Senior Leadership Team members (including the CEO,
  Chief, VP, and Managing Director levels of the organization), Board Members,
  Central Office Staff (if applicable; excluding the Leadership Team & CEO),
  Total teachers (anyone who spends more than 50% of their time delivering
  direct instruction to students in the classroom; and should NOT include
  instructional support staff, such as teaching aides, assistants, fellows,
  etc.), All School-Based Staff (non-instructional, school-based leadership
  roles)."
- Race/Ethnicity and Gender counts are only requested for 2025-26 (unlike the
  two Total # Staff rows, which cover both years), broken out by the same five
  categories.

## 5. Key Contacts Field Definitions

Fields: Active?; First Name; Last Name; Title; Email Address; Race/Ethnicity (+
Self Description); Gender (+ Self Description); Mobile Phone #; Roles 1-6; Data
Collection Participant?; Receives Data Collection Communication?

Definitions worth getting exactly right:

- **Race/Ethnicity Self Description** / **Gender Self Description**: conditional
  — only used for "prefer to self-describe" or when more than one category
  applies.
- **Mobile Phone #**: "only needed for CEO & Financial Lead for financial
  processing multi-factor authentication" — not a general-purpose field.
- **Roles 1-6**: functional areas for CSGF grant-making, communities of
  practice, or shared-learning communications. "Executive Lead" = most senior
  leader (CEO/ED/President) — max 2 contacts with this role. "Founder" =
  person(s) who created the school/org — max 2 contacts with this role.
- **Data Collection Participant?** vs. **Receives Data Collection
  Communication?** are easy to conflate but gate different things: the former
  controls portal/Sheet _access_; the latter controls _email_ communications
  only. (This is also why a task-reassignment target needs "Participant = Yes" —
  see the Portal mechanics section of the main skill file.)

## 6. School Finance (P&L) Field Definitions

(Note: CSGF's TOC lists this as "School Finance P&L Field Definitions" — the
actual header is "School Finance **(P&L)**," with parentheses. A literal string
search for the TOC wording will miss the real header.)

Fields: School Name; a shared-budget flag (whose "field name" is actually the
full instruction sentence, not a short label — see below); Philanthropic
Revenue; Total Revenue Including Philanthropy; Pesonnel Expenses (Salaries +
Benefits) [sic]; Management Fees; Facility Rent and/or Debt Service payments;
Total Expenses.

Definitions worth getting exactly right:

- **School Name / shared-budget flag**: "If you have schools that share a budget
  across schools, please put the financial data on the row for just one of the
  schools and leave the other(s) blank... Each school should have their own
  'school info' and 'facility' data populated." CSGF's own description
  references spreadsheet column letters (E, F-I, J-P) that only make sense next
  to the live submission sheet, not this definitions doc in isolation.
- **Philanthropic Revenue**: "All private restricted and unrestricted grants not
  listed above (do not include federal, state, or local grants)."
- **Management Fees**: "Payments that the school makes to the central office
  (e.g. general management fee, school startup, etc.)" — the org-level mirror of
  this is "Management Fee revenue" in Org Finance below (same transaction,
  expense side here, revenue side there).
- **Facility Rent and/or Debt Service payments**: annual rent, principal, and
  interest payments for the school's facility, for 2024-25.
- **All dollar figures in this section are for 2024-25** (prior year), unlike
  the Enrollment section above, which is keyed to 2025-26 — expected for a P&L
  filed in arrears, but easy to get wrong by defaulting to "current" year out of
  habit.

## 7. Org Finance Field Definitions

Only 5 fields: Total Recurring Public Revenue; Total Non-Recurring Public
Revenue; Other Revenue; Total Philanthropic Revenue; Management Fee revenue (if
applicable).

- **Total Recurring Public Revenue**: recurring local/state/federal revenue
  (IDEA, Child Nutrition, Title I-IV, E-Rate, local tax/lottery revenue).
- **Total Non-Recurring Public Revenue**: non-recurring sources (federal
  start-up, state/local start-up, i3, Race to the Top grants).
- **Other Revenue**: non-government, non-philanthropic revenue (uniform fees,
  interest, food revenue, etc.) — explicitly excludes intra-network transfers
  like management fees.
- **Total Philanthropic Revenue**: same "not listed above" boilerplate as the
  School Finance P&L section's Philanthropic Revenue — this is the org-level
  version of that school-level concept.
- **Management Fee revenue**: the revenue-side mirror of School Finance P&L's
  "Management Fees" expense — same transaction, opposite side.

---

## Structural notes on CSGF's own source doc

Flag these when citing the doc — they're CSGF-side inconsistencies, not ours,
and shouldn't be silently "corrected" when quoting:

1. Section titles in CSGF's table of contents don't always match the actual
   section headers (Enrollment section drops "Annual"; Finance section adds
   parentheses around "P&L"). Cite the real header.
2. An 8th, unlabeled block follows Org Finance: a single-column list of ~23
   Salesforce Portal field labels with `*` apparently marking required fields
   and **no descriptions at all**. The extraction **cut off mid-list** at
   "Administered iReady? \*" — treat this block as incomplete, not exhaustive,
   until re-checked directly against the live sheet.
3. Source typos: "Additional Contect" (should be "Context"); "Pesonnel Expenses"
   (should be "Personnel").
4. The Enrollment section reuses the exact same field label ("School
   Leader/Principal Demographics: Most Senior or Primary Leader") for two
   different rows with different intended content (primary leader vs.
   co-leader).
5. Two School Finance P&L descriptions (Philanthropic Revenue, Management Fees)
   carry trailing raw HTML-entity export artifacts (`&#13;`, `&#9;`) — strip
   these before reusing the text; they aren't real content.

All 7 named sections are present with real content — none are missing.
