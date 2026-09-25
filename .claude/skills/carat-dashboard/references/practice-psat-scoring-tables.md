# Practice PSAT 8/9 and PSAT 10 — College Board's published scoring tables

For converting PRACTICE PSAT raw scores. Official PSAT score files and their
student matching are a different job, in the `collegeboard-id-crosswalk` skill.

## Exception: PSAT 8/9 and PSAT 10 use official College Board tables

This file overrides Step 3 of _Procedure: Add practice assessments for a new
administration_ in [practice-assessments.md](practice-assessments.md). Run that
procedure for every other step, including its scaffold rows.

**Status: shipped for SY26-27.** 181 rows entered and audited clean (every
digest matches source). Use these as the format precedent:

| `assessment_id` | `scope`    | `scope_round` | `subject`           | `grade_level` | Rows | Raw  | Scale   |
| --------------- | ---------- | ------------- | ------------------- | ------------- | ---- | ---- | ------- |
| 226308          | `PSAT 8/9` | `PSAT891`     | Reading and Writing | 9             | 50   | 0-66 | 120-720 |
| 226309          | `PSAT 8/9` | `PSAT891`     | Mathematics         | 9             | 42   | 0-54 | 120-690 |
| 226310          | `PSAT10`   | `PSAT101`     | Reading and Writing | 10            | 49   | 0-66 | 160-760 |
| 226311          | `PSAT10`   | `PSAT101`     | Mathematics         | 10            | 40   | 0-54 | 160-760 |

`scope_round` has no underscore and keeps a trailing `1` — user's call, so do
not "normalize" it. The `1` leaves room for a second practice administration in
the same grade and year, which would otherwise sum into one bogus total (see the
BOY/MOY warning above).

**Outstanding verification on 226310 / 226311.** Illuminate syncs once nightly,
and these two were created after that run, so at entry time they were absent
from the warehouse — the question-count coverage check in Step 3 could not run,
and which ID holds which subject came from the user rather than from `title`.
226308 / 226309 did check out (66 and 54, matching the guide exactly). Confirm
226310 has 66 questions and 226311 has 54 once they land; a mismatch means the
wrong practice form or swapped subjects, and no other check will catch it.

PSAT 8/9 and PSAT 10 do not follow the practice-SAT path above. They use College
Board's **official** raw-score conversion tables, which differ in four ways that
break assumptions elsewhere in this skill.

**1. The source is a PDF, not an Excel paste. Ask for the PDF link.**

> Send the link to College Board's scoring guide PDF for the practice test in
> question. Don't send a screenshot — I can only read that by eye, and there's
> no way to check the numbers afterward.

The guides are public and predictably named:

```text
https://satsuite.collegeboard.org/media/pdf/psat-8-9-practice-test-1-scoring-guide.pdf
```

Download it and extract the table programmatically. **The page index differs per
guide** — PSAT 8/9 puts the conversion table on page 5 (index 4), PSAT/NMSQT on
page 6 (index 5). Locate it rather than assuming; the page carrying the scale
definitions is two before it.

**Extract by word COORDINATES, not `extract_text()`.** The table is laid out as
two side-by-side column-blocks (raws 0-33 left, 34-66 right). Flat text
extraction interleaves them, which produced a table that looked plausible and
was wrong — it manufactured phantom non-monotonic rows around raw 56 that do not
exist in the PDF. Group words into visual rows by `top`, split each row on an
x-coordinate threshold (~300 on a 612pt-wide page), then read each block
separately:

```bash
curl -sSL -o guide.pdf "<url>"
uv run --with pdfplumber python -c "
import pdfplumber
with pdfplumber.open('guide.pdf') as pdf:
    for w in pdf.pages[4].extract_words():
        if w['text'].strip().isdigit():
            print(w['text'], round(w['x0']), round(w['top']))
"
```

Within a block, rows read `raw rw_lower rw_upper math_lower math_upper` while
both sections are live, then `raw rw_lower rw_upper` past Math's maximum. Branch
on token count — 5 tokens carry both sections, 3 tokens carry Reading and
Writing only.

**Confirm anything surprising by rendering the region as an image** and reading
it. `page.crop(box).to_image(resolution=300).save(...)` settles a
source-anomaly-versus-parser-bug question in one step, and two text parses
agreeing is not proof — they can share the same layout misreading.

**If a screenshot is all that exists**, transcribe it twice independently — a
second reader working blind from the same image — and diff the two. A
single-digit misread is otherwise undetectable, because every downstream check
tests internal consistency rather than fidelity to the source. Never present
transcribed-from-image numbers as verified; say they are transcribed and
unconfirmed until something independent corroborates them. Precedent: one
screenshot transcription of 122 values came back exact when later diffed against
the PDF, which proves the method can work and not that it can be trusted.

**2. Use the `LOWER` column only.** The PDF presents each section as a
`LOWER`/`UPPER` pair per raw score. Take `LOWER`, and derive
`Raw_Score_Low`/`Raw_Score_High` by collapsing runs of consecutive raw scores
that share the same `LOWER` value — the same collapse rule as the practice SAT.
Ignore `UPPER` entirely.

**3. The two PSATs are on DIFFERENT scales.** This is the one with teeth:

| Test                | Section scale | Total    |
| ------------------- | ------------- | -------- |
| SAT                 | 200-800       | 400-1600 |
| PSAT 8/9            | 120-720       | 240-1440 |
| PSAT 10, PSAT/NMSQT | 160-760       | 320-1520 |

Do not carry one PSAT bound across both — a PSAT 10 row checked against 120-720
is 40 points out of range at each end and still passes. `SCALE_RANGE` in
`scripts/build_scale_score_rows.py` is keyed by the test label for exactly this
(the script still calls that field `Test_Type` internally); add an entry rather
than widening one.

**PSAT 10 has no separate scoring guide.** College Board publishes one practice
form for PSAT/NMSQT and PSAT 10 (same 160-760 scale), so the PSAT/NMSQT guide is
the source for PSAT 10 rows. Nothing in the document says "PSAT 10" — say so
plainly when reporting, and confirm the Illuminate assessment was built from
that same form before trusting the conversion.

**`scope` values**: use `PSAT 8/9` and `PSAT10`. These match the `scope` values
already in `int_assessments__college_assessment` (verified: `PSAT 8/9`,
`PSAT10`, `PSAT NMSQT`, alongside `SAT` and `ACT`) and the `benchmark_group`
prefixes in `_benchmark_calcs` (`PSAT 8/9_...`, `PSAT10/NMSQT_...`). Do not
invent a new spelling — `_benchmark_calcs` folds `PSAT10` and `PSAT NMSQT` into
one `PSAT10/NMSQT` threshold group, so the vocabulary is load-bearing beyond
this sheet.

**Grade level**: PSAT 8/9 is grades 8-9, PSAT 10 is grade 10, which puts these
rows adjacent to the historical `× 10` rescale path. That guard is
`scope = 'SAT' and subject_area in ('Reading', 'Writing') and grade_level in (9, 10)`.
A PSAT row with `Subject = 'Reading and Writing'` does not match the subject
list, so it does not fire today — but any future change to that predicate must
not widen it to catch these.

**Verified against PSAT 8/9 Practice Test 1** (`2324-P89-773`): sections are on
a 120-720 scale, total 240-1440, Reading and Writing raw 0-66, Math raw 0-54.
Those raw maxima match Illuminate's question counts, so the usual coverage check
still applies.

**The conversion table is per practice test.** Practice Test 1 and Practice Test
2 have different tables. Establish which practice test each Illuminate
assessment corresponds to and fetch that test's PDF — the same PT1/PT2 mapping
the practice SAT needs. Never reuse one test's table for another.

**4. A real typo in PSAT 8/9 Practice Test 1's Reading and Writing table, and
the one sanctioned deviation from a published table.** Raw 65 maps to 710 and
raw 66 — a perfect raw score — maps to 700, so a student answering everything
correctly would read 10 points below one who missed a question. Confirmed
against the rendered PDF, so it is College Board's error, not a transcription
slip.

**Decided and shipped: raw 66 is entered as 720** for assessment 226308, which
is both the section maximum and that row's own `UPPER` value. This is the only
place the sheet knowingly diverges from a published table.

The correction lives in `SCALE_CORRECTIONS` in the generator, not as an
exemption from the monotonic check — the check stays fatal, because its real job
is catching column misalignment during parsing, and a quiet exemption would
retire a working guard to accommodate one bad cell. The generator prints every
correction it applies and aborts on a stale entry (one naming a raw score that
is absent, or one the source now already agrees with).

**No downstream check can detect a corrected value**, which is why it is
recorded here, in the reference doc, and in the generator's comments.

There is a second inversion in `UPPER` at raw 56-57 that does not affect us.
Both exist because, per the guide's own scale-definition page, the paper scoring
method is "a simplified (and therefore slightly less precise) version of the one
used in the actual test." Math has no inversion.

**PSAT 8/9 cannot reach its scale maximum**, typo aside: Reading and Writing
tops out at 710 and Math at 690, so a perfect raw score converts to 1400 (1410
with the correction), not 1440. Published behavior, not an entry error. Both
PSAT 10 sections do reach 760, so PSAT 10 does reach 1520.

**Consequence of `LOWER` specific to PSAT**: these bands are far wider than the
practice SAT's — mean width 54 points for Reading and Writing and 51 for Math,
against roughly 20 for the SAT tables, reaching 100 points at the low end.
Taking `LOWER` therefore flattens the floor hard: Reading and Writing raws 0
through 6 all map to 120, so a student improving from 0 to 6 correct shows no
movement. This is consistent with the shipped SAT rows, which flatten raws 0-8
to 200, so `LOWER` remains the convention — but expect the question and have
this answer ready.
