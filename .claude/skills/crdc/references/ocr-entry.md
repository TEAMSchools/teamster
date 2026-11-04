# Entering data on the OCR site

OCR's submission system is a website; each district's CRDC contact gets an email
when it opens for the cycle (for SY2025-26, expected fall 2026, possibly
December 2026). KTAF enters every value by hand. Claude cannot log in; the user
types, and Claude helps check values and draft flag responses.

## Before entry

- Every district that files needs its own login. Confirm Camden's and Newark's
  logins still work. For Paterson, the open question is: how do we get access to
  the Paterson instance of the CRDC submission system? Paterson is its own
  district in OCR's system. Raise it with the data team lead before the system
  opens, and do not start Paterson entry until someone has a login.
- The collection sheet is complete for the region, or the gaps are listed in the
  kickoff doc with a reason.
- The data review items (law enforcement referrals, arrests, physical restraint,
  harassment or bullying) have had their second look.

## Order of entry

1. The LEA form (the `DF - ` tabs) for the district.
2. The school form (the `SF - ` tabs). Each region reports all its schools as
   one school, so there is one school form per district.
3. Indicator questions (yes/no) before the counts behind them; the answer can
   change which count questions the site asks.
4. Multi-value cells go in the form's order, left to right, as stored in the
   collection sheet.

## Quality flags

The site checks values and raises flags such as:

- "Values are extremely high compared to LEAs with similar characteristics."
  Common for KTAF because each region reports all its schools as one school,
  which makes one "school" far larger than a typical one.
- "It is unlikely that the value(s) entered for students disciplined for
  harassment or bullying would be greater than the value(s) entered for..."
  Cross-checks between related items.

For each flag:

1. Recheck the value against its source: the workbook count, or the owner's tab.
   For a model count, rerun the check in
   [model-and-workbook.md](model-and-workbook.md) → A count looks wrong.
2. If the value is wrong, fix it in the collection sheet first, then on the
   site.
3. If it is right, give OCR's site a short reason. Record the flag text in the
   tab's Audit Reason column and the reason in Correction Reason Details, so the
   next cycle has it. Last cycle's reasons are in the prior collection sheet;
   reuse the wording when the situation is the same. Several SY2023-24 flags
   were answered "Data is correct".
4. Write reasons in plain language, with no student details. They are part of
   the submission.

## Close out

- Every flag answered, every form complete, then the district contact certifies.
  Certification is per district: three for SY2025-26.
- Mark each tab 100% on the collection sheet's Home tab.
- Leave the filled collection sheet and kickoff doc in the cycle subfolder as
  the record. Nothing from the submission goes into the repo.
