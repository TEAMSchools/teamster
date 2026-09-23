# Procedure: Roll the assignment expectations over to a new year

**Trigger phrases:** "we have to add gradebook audit count rows to PowerSchool",
"we need to roll over to the new year for the PS plugin", "T&L sent the new
year's gradebook expectations sheet", "the audit is still reporting against last
year's expectations"

**The academics team owns this, and the mechanics are not here.** They run it
from the `gradebook-expectations-upload` Claude skill, which reads the planning
sheet and emits the upload CSVs. That skill is the source of truth for the
generation rules -- the week mapping, the per-column fill, the per-instance
split -- and it lives in this repo, alongside the plugin it feeds, at
[`ps-plugins/skills/gradebook-expectations-upload/`](../../../../ps-plugins/skills/gradebook-expectations-upload/SKILL.md).
Building and deploying the plugin itself is covered in
[`maintain-the-plugin.md`](maintain-the-plugin.md); shipping a change to this
chat skill is covered in [`ship-a-skill-update.md`](ship-a-skill-update.md).

The `ps_plugin_data` tab (the IMPORTRANGE Sources tab feeding the
`Template QW-Date Crosswalk` Reports tab -- see
[`../references/published-sheets.md`](../references/published-sheets.md))
carries `week_start_monday` and `week_end_friday` so academics can match a week
number to the actual calendar dates while filling in counts -- a reading aid for
a person, not part of the upload and not something the skill computes from.
Because the sheet already resolves week numbers to dates, the chat skill does no
week-mapping arithmetic at all, which is the single biggest reason this work is
safe to hand to a chat session.

Deliberately a pointer and not a copy. This procedure used to carry the full
mechanics; two copies of a fill rule drift, and when they disagree nobody can
tell which is right. If you are asked for the mechanics, read that skill's own
source rather than reconstructing them here.

## The replacement rule, and the quiet failure

`U_EXPECTATIONS` has no `academic_year` column -- it reflects whatever is live
in PowerSchool right now, which is why
`int_powerschool__u_expectations_qtd_unpivot` stamps the year as a literal. Its
key is effectively `(instance, school_level, quarter, week_number)`, so two
years cannot coexist: a new-year row replaces its same-numbered predecessor
rather than sitting beside it.

That key is also why replacement is **per quarter**, not all-or-nothing.

**The normal process is all four quarters in one swap.** No standing debt, one
sitting, done. Document and expect that.

**Some years academics is behind**, with only the current quarter decided. That
is a legitimate degraded path, not a reason to refuse: Q1 is being taught now
and needs correct expectations now. Replace what is decided, and be explicit
about what is not.

**The rule that actually binds: each quarter's rows must be replaced before that
quarter starts.**

The failure this guards against is quiet, which is why it is worth stating
carefully. An unreplaced future quarter is harmless in October and wrong the
Monday it opens -- and it does not blank. It serves last year's counts, which
are plausible numbers, so the audit silently misreports whether teachers entered
enough assignments for that entire quarter. Nothing fails and no test catches
it. A blank dashboard gets reported within a day; a wrong expectation does not.

So the question to ask is never "are all four quarters ready" but "is the
quarter we are in, and the one starting next, correct". If someone asks you to
roll the year over with one quarter in hand, do it -- and tell them which
quarters still carry last year's numbers and the date each becomes wrong.

**For that date to be stateable, the `ps_plugin_data` grid should carry all four
quarters' week rows with their dates from the start, counts left blank where
academics has not decided.** With those rows present, `week_start_monday` gives
the exact deadline ("Q2 opens Monday 11/2 and still has last year's counts").
Without them an undecided quarter has no Monday in the sheet, and the warning
degrades to "sometime later", which nobody acts on. This is the same reasoning
as [#4917](https://github.com/TEAMSchools/teamster/pull/4917), which pivoted the
template wide so a category with no count shows as a blank cell to fill rather
than silently vanishing as a missing row -- the same principle one level up, for
quarters.

## What stays on this side

Neither half of this is complete alone: the data team cannot write to
PowerSchool, and academics cannot run the verification. After they load, confirm
via the query in the
[reference doc's](../../../../docs/models/gradebook-audit-data-model.md) Step 1:
zero null counts, week counts matching `int_students__calendar_week`, four rows
per `region x school_level` out of
`int_powerschool__u_expectations_qtd_unpivot`, and the four-row
`category_summary` floor intact.

That query is also the fallback path. If academics is blocked, a data-team
member can generate the CSVs from `int_students__calendar_week` and the planning
sheet directly -- but read the chat skill's rules first, and hand the upload
back, because the delete-and-load happens in the plugin.
