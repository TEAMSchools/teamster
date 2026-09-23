# Gradebook Expectations Upload — install and first run

For the Teaching & Learning / Academics team. No technical background needed.

## What this is

A skill that turns the weekly assignment counts you decide (W/H/F/S) into what
PowerSchool's Gradebook Audit plugin needs — and walks you through it, whether
you're starting a new year, updating a quarter, or trying to figure out why the
dashboard looks wrong.

The gradebook audit dashboard compares what teachers actually entered against
those counts. If the counts are wrong, the dashboard is wrong — quietly, with no
error message anywhere. That is why the skill checks everything before anything
is uploaded, and why you should not skip those checks.

## Install it

In **Claude Desktop**:

1. Click **your name** (bottom left) → **Settings** → **Skills**.
2. Click **Add**, then **Upload skill**, and choose the zip the data team sent
   you — it is named `gradebook_expectations_upload_v<version>.zip`, e.g.
   `gradebook_expectations_upload_v1.0.0.zip`. Upload **the zip file itself. Do
   not unzip it first.** It is already packaged the way Claude expects.
3. The skill appears in your list. Make sure its toggle is **on**.

Anthropic's own instructions, if the screens here look different:
<https://support.claude.com/en/articles/12512198-how-to-create-custom-skills>

### If there's no Skills section, or no way to add one

Skills have to be turned on for the whole organization before anyone can add
one. This is not something you can fix from your own settings — email the data
team and ask them to sort it out.

## Before your first run

Three things have to be ready:

- **The Google Drive connector must be connected in Claude.** The skill reads
  two spreadsheets and nothing else — Academics' planning sheet and the data
  team's **Gradebook Audit Template** sheet. No databases, no PowerSchool. If
  Drive isn't connected it cannot start.
- **Code execution must be turned on.** The skill needs it to write the CSV
  files you download; without it the skill can do the arithmetic but cannot hand
  you a file. It is an organization setting rather than one in your own
  settings, so if it turns out to be off, ask the data team.
- **The planning sheet**, with the quarter(s) you want decided and filled in.
  You don't need to tell Claude which quarters — it checks the sheet itself and
  tells you what it found decided versus still in progress. It's fine if only
  some quarters are ready; it handles that and tells you the deadline for the
  ones you're leaving.

## Start it

Just say what you need in your own words — the skill figures out which of three
things you're asking for:

- **Starting a new school year:** "We need to load the gradebook expectations
  for the new year." / "Roll over the gradebook expectations."
- **Updating mid-year:** "T&L decided the counts for Q2 — can you get them into
  PowerSchool?" / "The audit is showing last year's expectations."
- **Something looks wrong:** "The gradebook audit dashboard looks off, can you
  help me figure out why?" / "Why isn't this updating?"

It already knows which sheets to read, and will tell you which file and tab it
opened. If it names anything other than the planning sheet or the **Gradebook
Audit Template** sheet, stop it and tell the data team.

## What it does, and where it stops

For loading counts in (new year or mid-year update), it reads the grid, fills in
any blank counts using the rule the data team agreed, and builds **one CSV per
region** — Camden, Newark, Paterson — because each region is a separate
PowerSchool instance. You download each one straight from the conversation.

It shows you every file as a table in the conversation before anything is
uploaded. **Read those tables.** They are how a wrong repeated week gets caught
while it is still cheap to fix.

Then it runs several checks, including comparing its own math against what's
already correctly in PowerSchool. If any check fails it stops and tells you what
failed instead of uploading.

For "something looks wrong," it doesn't build or upload anything by default — it
compares what's in PowerSchool against what Academics decided and tells you what
it finds. Most of the time the fix, if there is one, is a single row, not a
whole reload.

## ⚠️ You need PowerSchool access for the actual upload

Building and checking the files needs nothing but Claude and the spreadsheets.

**Actually uploading needs a PowerSchool admin account that is a member of the
`Gradebook Group` security group, on each region's instance.**

If you don't have that, the skill will stop before touching PowerSchool and say
so. That is the correct outcome, not a bug. Send the files it produced to the
data team and let them do the load. **Do not try to work around it** — the
upload involves deleting existing rows, and getting that wrong takes the
dashboard down for every school in a region.

## Two things not to skip

- **The checks before uploading.** They exist because a typo in a count
  misreports every teacher in a region, and nothing downstream will flag it.
- **Telling the data team what you loaded, the next day.** They run a
  verification you can't: that nothing came through empty, that the week counts
  match the school calendar, and that the dashboard's category rows are intact.
  The job isn't finished until they confirm it landed.

## Who to contact

The KTAF Data Team — data@kippnj.org.

Contact them if a check fails and you can't see why, if the numbers in the grid
look implausible, if an upload half-finishes, or if a troubleshooting session
turns up something that affects more than one region or quarter. Also tell them
if PowerSchool's screens stop matching what the skill describes — that means the
plugin changed and the skill needs updating.
