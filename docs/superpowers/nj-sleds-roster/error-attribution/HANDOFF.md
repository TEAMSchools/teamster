# Handoff — attributing NJSLEDS upload errors

## What you are picking up

NJSLEDS has cut back its service level because of capacity problems. It still
accepts and processes Course Roster uploads, but it now only produces the
detailed error report overnight, somewhere around midnight to 1am the next day.

So when you upload a file, you get back a number — "23 errors" — and nothing
else. No record list, no field names, no rule references. Waiting a day per
attempt does not fit inside the submission window, and checking by hand does not
scale and never tells you when you are finished.

Your job is to work out what those errors are on the same day, using the
handbooks' own validation rules.

## The idea

Both Course Roster handbooks document every validation rule explicitly, as "An
error will occur if..." statements. There are 122 of them — 54 for staff, 68 for
student. They have all been extracted and turned into code you can run against
the file you uploaded.

So instead of guessing, you get a count per rule. If the state says 23 errors
and one rule is violated on exactly 23 rows, that is almost certainly your
answer.

The state's count is the only feedback it gives you, so use it as the test:

1. Run the tool against the file you uploaded, with the count the state gave
   you.
1. Take the most likely explanation.
1. Fix it at source in PowerSchool.
1. Re-pull, re-upload.
1. Check the count dropped by exactly the amount that rule predicted.

A clean match confirms it. A partial drop means the rule was real but there is
more. No drop means it was the wrong guess — cross it off and take the next
candidate. A few cycles of this maps the whole error set without ever waiting
for the overnight report.

## Setup

You need a clone of the `TEAMSchools/teamster` repo and `uv`. Nothing else — no
BigQuery access, no dbt, no warehouse credentials.

```bash
git clone https://github.com/TEAMSchools/teamster.git
cd teamster/docs/superpowers/nj-sleds-roster/error-attribution
```

**You do not need the handbook PDFs.** The rules are already extracted into
`handbook-rules-staff.md` and `handbook-rules-student.md`, which are committed.
The PDFs themselves live in a gitignored scratch folder and will not be in your
clone.

**You do need the upload files** — the CSVs PowerSchool generates. Use the exact
file you uploaded to the state, not a fresh re-pull. A re-pull can differ from
what the state actually saw, and then you are explaining the wrong file.

## Using it

Run from inside the `error-attribution` directory.

```bash
uv run python attribute_errors.py "/path/to/NJ_Student_Course_Submission.csv" --errors 23
```

It works out whether the file is a staff or student submission from its header.

To see which rows a specific rule is flagging:

```bash
uv run python attribute_errors.py "/path/to/file.csv" --rule STU-CREDITSEARNED-RANGE
```

That prints local IDs and section codes so you can find the records in
PowerSchool. It deliberately leaves out names, dates of birth, and state IDs.

If you would rather just describe the situation to Claude, there is a skill that
picks all this up: tell it something like "NJSLEDS says 23 errors on the student
upload but won't give me detail until tomorrow" and it will run the right thing.

## Reading the output

Four sections, in the order you should trust them:

| Section                              | What it is                                                                                                    |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| Handbook rule violations             | Count per rule, with the handbook page and exact wording. This is evidence.                                   |
| Attribution                          | Rule combinations that sum to the state's count. This is inference.                                           |
| Additional local findings            | KTAF expectations the handbook does not require. The state never checks these, so they cannot be your answer. |
| Rules that cannot be checked locally | Where an unexplained leftover probably lives.                                                                 |

Two things to keep in mind:

**Prefer single-rule explanations.** If four rules happen to add up to 23, that
is usually coincidence. One rule violated on exactly 23 rows is a real lead.

**The count is ambiguous.** The state may mean 23 bad rows, or 23 bad fields
across fewer rows. The report gives you both numbers. Check the target against
both before you commit to a theory.

## What it cannot tell you

Some rules need something the file alone does not contain, and those are marked
with the reason rather than guessed at:

- The staff five-field identity match needs the state's Staff Management export.
- SCED subject-area and course-identifier validity needs the NCES SCED code
  list.
- The dual-enrollment institution check needs the NJSLEDS OPE ID list.

If the numbers do not add up, the answer is probably in that list. Say that
rather than inventing a cause — a confident wrong guess costs more than an
honest "I don't know yet," because someone will go and act on it.

## When the numbers still don't add up

If the state's count is higher than anything the rules explain, the leftover is
the **residual**, and the tool does one more thing automatically: it tests its
own assumptions against it.

A few values in this tool are assumptions rather than handbook facts — mainly
the school-year date window, which has no cited source. If one of those is
wrong, it could be the residual's cause. So the report sweeps each assumed value
against a few candidates and tells you whether any of them would produce exactly
the missing count.

Most of the time on current data it comes back negative, and that is genuinely
useful: it rules the assumptions out and points you at the not-locally-checkable
rules instead, which is where the leftover probably lives. When it does find a
match, treat it as a lead to confirm by fixing and re-uploading — not as an
answer.

One thing it deliberately will not do: change a value to make the file look
cleaner. Testing whether an assumption explains a count the state already gave
you is legitimate. Retuning a rule until the file passes hides real errors —
that mistake has already been made once on this project and is documented in
`rules.py` so it isn't repeated.

## Please record what you learn

On [issue #4659](https://github.com/TEAMSchools/teamster/issues/4659), after
each upload cycle, note:

- the count the state reported
- which rule you thought it was
- whether the count dropped by the predicted amount

That record is what makes the next cycle faster, and it is the only way we find
out which rules the state actually enforces versus merely documents. It is lost
if nobody writes it down.

**Counts and rule ids only.** These files carry student and staff names, dates
of birth, and state IDs. Never put a row, a name, a date of birth, or an ID in
an issue, a pull request, Slack, or anywhere else outside your machine.

## If a rule looks wrong

It might be. The catalog was built by reading 122 handbook statements and
turning each into code, and a misread is possible. The verbatim handbook wording
sits right next to each rule in the report — if the code and the wording
disagree, the wording wins. Flag it on the issue and it gets fixed.

## Where things are

| File                                         | What it does                                          |
| -------------------------------------------- | ----------------------------------------------------- |
| `attribute_errors.py`                        | The tool you run                                      |
| `rules.py`                                   | Rule structure and shared value helpers               |
| `rules_staff.py`                             | The 54 staff rules                                    |
| `rules_student.py`                           | The 68 student rules                                  |
| `handbook-rules-staff.md`                    | Extracted Staff handbook text, v1.1 May 2026          |
| `handbook-rules-student.md`                  | Extracted Student handbook text, v1.4 July 2026       |
| `.claude/skills/nj-sleds-error-attribution/` | The skill, so Claude picks this up from a description |

Wider context for the submission itself, including the audit runbook and the
helper-query pack, is in
[issue #4280](https://github.com/TEAMSchools/teamster/issues/4280).
