---
paths:
  - "**/src/dbt/**/*.yml"
  - "**/src/cube/**"
---

# FERPA and PII: what counts, and how this repo handles it

Loads on the first read of dbt YAML or a Cube file. Distilled 2026-09-09 from
the U.S. Department of Education's student privacy site and the regulation it
links to. The outbound rule (never emit PII values to PR comments, issues,
Slack, Asana, or agent output) lives in the root CLAUDE.md _Never_ block; this
file decides what "PII" means when you apply it.

Sources, in order of authority:

- Regulation: 34 CFR Part 99, especially
  [§99.3 Definitions](https://www.law.cornell.edu/cfr/text/34/99.3) and
  [§99.31 Disclosure without consent](https://www.law.cornell.edu/cfr/text/34/99.31).
  The eCFR blocks automated fetches; the Cornell LII mirror carries the same
  text.
- Department guidance:
  [studentprivacy.ed.gov/ferpa](https://studentprivacy.ed.gov/ferpa), the
  [PTAC glossary](https://studentprivacy.ed.gov/glossary), and PTAC's
  [Data De-identification: An Overview of Basic Terms](https://studentprivacy.ed.gov/resources/data-de-identification-overview-basic-terms)
  (PDF).

This is a working reference for engineering decisions, not legal advice. A
question about a specific disclosure, a data-sharing agreement, or a parent
request goes to legal or People Operations.

## Scope

FERPA covers every "educational agency or institution" that receives federal
education funds. KTAF's schools and the network office are covered.

An **education record** is any record "directly related to a student" and
"maintained by an educational agency or institution or by a party acting for the
agency or institution" (§99.3). Nearly every student-level table in this
warehouse qualifies. Records about staff that "relate exclusively to the
individual in that individual's capacity as an employee" are not education
records. Staff PII is still protected, by policy rather than FERPA; the Cube
`staff_pii` split in `.claude/rules/cube-authoring.md` is that policy.

## The definition (§99.3, verbatim)

"Personally Identifiable Information. The term includes, but is not limited to:

- (a) The student's name;
- (b) The name of the student's parent or other family members;
- (c) The address of the student or student's family;
- (d) A personal identifier, such as the student's social security number,
  student number, or biometric record;
- (e) Other indirect identifiers, such as the student's date of birth, place of
  birth, and mother's maiden name;
- (f) Other information that, alone or in combination, is linked or linkable to
  a specific student that would allow a reasonable person in the school
  community, who does not have personal knowledge of the relevant circumstances,
  to identify the student with reasonable certainty; or
- (g) Information requested by a person who the educational agency or
  institution reasonably believes knows the identity of the student to whom the
  education record relates."

Items (a) through (e) are direct identifiers: PII on their own. Item (f) is the
test for everything else. PTAC's glossary names the indirect identifiers it has
in mind: "gender, birth date, geographic indicator and descriptors." PTAC's
de-identification paper adds that "simple removal of direct identifiers from the
data to be released DOES NOT constitute adequate de-identification."

## Directory information

§99.3 lets a school designate some fields as **directory information**:
"information contained in an education record of a student that would not
generally be considered harmful or an invasion of privacy if disclosed."
Examples in the regulation: name, address, telephone, email, photograph, date
and place of birth, grade level, enrollment status, dates of attendance,
activities and sports, honors and awards, most recent school attended. It "does
not include a student's social security number or student identification (ID)
number."

Designation is a policy act with parent opt-out, not a property of the column.
Do not treat a field as freely disclosable because the regulation lists it as
directory-eligible. Unless the user confirms KTAF's directory designation and
opt-out handling, treat every field above as PII.

## De-identified data (§99.31(b))

A release needs no consent "after the removal of all personally identifiable
information provided that the educational agency or institution or other party
has made a reasonable determination that a student's identity is not personally
identifiable, whether through single or multiple releases, and taking into
account other reasonably available information."

Two consequences for this repo:

- **Aggregates are not PII, until the cell is small.** A count by school and
  grade is fine. A count by school, grade, race, and IEP status can be a cell
  of 1. PTAC's answer is suppression, including complementary suppression so the
  hidden cell cannot be recovered from totals. The repo has no automated
  small-cell suppression
  ([#4237](https://github.com/TEAMSchools/teamster/issues/4237)); a Cube
  aggregate view that slices by a demographic is a decision, not a default.
- **A record code for a de-identified release** must not be based on "a
  student's social security number or other personal information," and the
  releasing party may not "disclose any information about how it generates and
  assigns a record code" (§99.31(b)(2)). An SIS primary key or `student_number`
  fails both tests. Generate a fresh code for any de-identified extract.

## Disclosure inside the network (§99.31(a)(1))

Staff may see PII when they are school officials with a "legitimate educational
interest," and the agency "must use reasonable methods to ensure that school
officials obtain access to only those education records in which they have
legitimate educational interests." Cube's row-level access and PII defaults are
those reasonable methods. That is why natural-language questions go through Cube
(root CLAUDE.md, _Tool selection_) and why a raw-warehouse answer that bypasses
it needs a reason.

## Decision procedure for a column

Work down the list; stop at the first match.

1. **Direct identifier: tag it.** Name and name parts (`*_name`, `lastfirst`),
   parent or guardian or contact fields, street address or city or zip, `ssn`,
   `student_number`, `state_id` and other state or district student numbers,
   `local_id`, kippadb `school_specific_id`, `employee_number`, email, phone,
   photo, `dob` or `birth_date`, place of birth, biometric data, credentials or
   tokens.
2. **Free text about a person: tag it.** `comment`, `note`, `entry`, `remarks`
   on a student or staff table. Free text routinely carries names and
   circumstances.
3. **Student-level education content: tag it.** Grades, GPA, credits, assessment
   scores, daily attendance, discipline, IEP or 504 or disability, EL status,
   FRL or economic status, race or ethnicity, gender, home language, graduation
   pathway, program enrollment. Each is item (f) information: linked to a
   specific student and identifying in combination. Tag at the row grain it is
   stored at; a student-level model with these columns is PII even when it
   carries no name.
4. **Surrogate keys: do not tag, but do not export.** `studentid`,
   `studentsdcid`, `dcid`, `id`, `*_key`, dlt or Focus internal ids. The
   regulation's "student number" is the number the school uses to identify the
   student, which here is `student_number`. A database key resolves to a person
   only through a table that is already PII, so a "reasonable person in the
   school community" cannot identify the student from it. Repo precedent agrees:
   no `studentid` or `studentsdcid` column carries a tag. The limits: a key is
   still linkable, so it never leaves the warehouse in an outbound file next to
   content, and it is never a record code for a de-identified release.
5. **Aggregates: do not tag.** Counts, rates, and averages over a group. Watch
   small cells (above).
6. **Reference data: do not tag.** Courses, sections, schools, terms, calendars,
   codesets, grade scales, plan structures such as `int_powerschool__gpnode`. No
   student in the row.

When a model mixes tiers, tag the columns, not the model. When a whole model is
student-level content with no reference-only columns, a model-level tag is
acceptable; both forms are `config.meta.contains_pii: true`.

## Repo conventions that follow

- **Tag at the column.** Precedent in `src/dbt/powerschool` staging is
  column-level `config.meta.contains_pii: true`; follow it in new YAML. The
  existing staging tags are narrower than tier 3 (they omit gender, race, and
  grades). Widen them when you touch a file for another reason; do not sweep.
- **A PII-heavy new model** gets a one-line confirmation of scope with the user
  before tagging: direct-only, or direct plus student-level content. The default
  when no one answers is tiers 1 through 3.
- **Outbound surfaces** (PR comments, issue bodies, Slack, Asana, scheduled
  agents): redact values from any tier-1 through tier-4 column to `Student A` or
  to the column name before posting. Aggregates with no small cell may go out as
  numbers. The row content of a query result is PII even when the query had no
  name column.
- **Staff data** is outside FERPA but not outside policy. `staff_pii` in Cube
  and the root CLAUDE.md line about staff contact information govern it.
