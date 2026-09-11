# Cumulative GPA Monitor Dashboard Guide

School Year 2026-27. For KIPP Forward and high school leadership teams in Newark
and Camden.

Notes for the designer: build this as a Zendesk Guide article using the KIPP NJ
| Miami Zendesk snippets (`design_system/kippnj-miami-design/zendesk/`, read its
README first). Lines beginning `> **Callout:**` are callouts; drop the word
"Callout:" when rendering and use the Note style unless the text warns about a
mistake, then use Warning. Italic lines beginning "Caption:" directly under an
image are that image's caption; drop the word "Caption:". Image references point
at `screenshots/` next to this file; upload each to Guide media and swap in the
hosted URL. Put a table of contents after "What this dashboard does", linking to
the four numbered sections, the two walkthroughs, Quick answers, and the
Glossary. Student names are pixelated in every image that had them; do not
re-crop. The screenshot manifest is a production note, not reader content.
On-screen control names appear in bold exactly as the dashboard shows them.

Prompt for Claude Design (paste as-is, with this file attached):

```text
Build a Zendesk Guide help-center article from the attached Markdown file,
"Cumulative GPA Monitor Dashboard Guide", using the KIPP NJ | Miami Zendesk
article subsystem in design_system/kippnj-miami-design/zendesk/. Read that
folder's README.md first and follow its rules exactly: every block is a table
with inline styles and literal hex, no <style>, no var(), no flex or grid,
margin only on <table>, <div> not <p> inside cells, system font stack, weights
400, 600 and 700 only, headings semibold uppercase with sentence-case words.
Use the snippets in index.html for callouts, screenshot blocks, tables, and the
table of contents. Match sample-article.html for overall structure.

Structure: do not repeat the title; Zendesk renders it. Start with the
audience line as the summary. Then an "In this article" table of contents
linking to: Three words to know, Set the controls, Read the top row, Read the
charts, Find the students, Two walkthroughs, Quick answers, Glossary. Then the
body in the order of the Markdown. Heading levels never skip. Anchor ids are
lowercase and hyphenated.

Rendering rules: a line beginning "> **Callout:**" is a callout; drop the word
"Callout:" and use the Note style, except use Warning when the text warns about
a mistake (the grade 9 on-the-books callout, the Grade view callout). An italic
line beginning "Caption:" under an image is its caption; drop the word
"Caption:". Every image reference points at screenshots/<file>; place each as a
screenshot block with its caption, full width, no crop, no rounded corners.
Keep every Markdown table as a table. Numbered lists are step sequences, one
action per step. Bold on-screen control names exactly as written. Keep the
wording; do not paraphrase, shorten, or add emoji.

Leave out: the "Notes for the designer" paragraph, this prompt, and the
"Screenshot manifest" section.

Links to keep live: the Tableau dashboard link and the suite guide. End with a
"Related articles" list of the suite guide and the Academic Health Dashboard
Guide.

Output one HTML file ready to paste into the Zendesk article body, plus a list
of the screenshot files in the order they appear.
```

---

## What this dashboard does

The Cumulative GPA Monitor answers one question: **are our high school students
on track to finish this year with a cumulative GPA of 3.0 or better, and which
students are close?**

It is one tab in the Tableau workbook **Academic & Gradebook Health Suite**.
Open it here:
<https://tableau.kipp.org/t/KIPPNJ/views/AcademicGradebookHealthSuite/CumulativeGPAMonitor?:embed=y>

It covers grades 9 through 12 at KHS, NCA, and NLH. Data refreshes overnight.
The other tabs in the suite are described in the
[Academic & Gradebook Health Suite guide](https://teamschools.zendesk.com/hc/en-us/articles/43413797842071-Academic-Gradebook-Health-Suite).

![The Cumulative GPA Monitor](screenshots/01-cgm-full.png)

_Caption: The whole tab. Controls across the top, four tiles, a goal row, then
four charts. The default view is grade 11._

---

## 1. Three words to know

Everything on this tab uses the same kind of GPA. Three words describe it, and
the rest of the guide assumes you know them.

**Cumulative.** Every high school year the student has completed, plus this one.
A junior's cumulative GPA covers grades 9, 10, and 11. This is different from
the Y1 GPA on the Academic Health tabs, which is this year only.

**Unweighted.** Every course counts the same. An A in AP Biology and an A in
Biology add the same amount. This is the GPA colleges see on the transcript,
which is why this tab uses it.

**Projected.** What the cumulative GPA will be in June if the student's current
course grades hold to the end of the year. The tab also shows **on the books**,
which is the cumulative GPA from grades already posted. Early in the year, on
the books means last year's grades. By June the two numbers meet.

> **Callout:** A 3.0 cumulative unweighted GPA is the line this tab is built
> around. Every goal, tile, and chart measures how many students are at or above
> it.

---

## 2. Set the controls

![Header and controls](screenshots/02-cgm-header-controls.png)

_Caption: The title strip with the two panel buttons, and the five controls
below it._

| Control           | What it does                                                                                                                                                         |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Academic Year** | This year or last year. Last year is closed, so projected and on the books are the same there.                                                                       |
| **Region**        | All, Newark, or Camden. Also switches the goal the tab compares against, from the network goal to that region's goal. Paterson has no high school and shows nothing. |
| **Grade view**    | Grade 9, 10, 11, or 12. Changes the four tiles, the goal row, the band mix chart, and the Cusp Roster. The two charts on the right always show all four grades.      |
| **GPA basis**     | **Projected EOY** or **On the books today**. Changes which cumulative GPA the percentages use. See the callout below for what it does not change.                    |
| **School**        | One or more of KHS, NCA, NLH. Narrows everything.                                                                                                                    |

> **Callout:** **Grade view** does not reach the two charts on the right side.
> They always show grades 9 through 12 so you can compare. If you change the
> grade and those charts do not move, that is expected.

> **Callout:** Leave **GPA basis** on **Projected EOY**. The goal row, the
> "students below 3.0" tiles, and every color on the tab are always projected,
> whatever the switch says. Switching to **On the books today** changes only the
> two percentage tiles, the by-grade bars, and the Cusp Roster values. Each
> panel prints which basis it is showing in grey, so you can always check.

---

## 3. Read the top row

### The four tiles

![Four tiles](screenshots/03-cgm-four-tiles.png)

_Caption: The four tiles for the grade chosen in **Grade view**. The grey line
under each title says whether it follows the basis switch._

| Tile                              | What it means                                                                                                           |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **At 3.5+ cumulative**            | Share of the grade at or above a 3.5 cumulative GPA.                                                                    |
| **At 3.0+ cumulative**            | Share of the grade at or above 3.0. This is the number the goals are set against.                                       |
| **Students below 3.0**            | How many students in the grade are projected to finish under 3.0.                                                       |
| **Of those, can still get there** | How many of those students could still reach 3.0 by June with strong grades this year. The rest cannot, no matter what. |

Hover a tile for the counts behind the percentage.

### The goal row

![Goal row](screenshots/04-cgm-goal-row.png)

_Caption: Gap to goal and students still needed, for the grade chosen in **Grade
view**._

**Gap to goal** is the projected share at 3.0+ minus this grade's goal, in
percentage points. Green means the grade is at or above its goal. Red means
below.

**Students still needed** is how many more students at 3.0+ it would take to
reach the goal. It reads 0 once the goal is met.

The goal is the network goal, or the region's goal when **Region** is set. This
year's goals for cumulative 3.0+ are the same at every school.

---

## 4. Read the charts

### Band mix for the selected grade

![Band mix, network](screenshots/05-cgm-band-mix-network.png)

_Caption: Two bars for the selected grade. The top bar is on the books today,
the bottom bar is projected to year end. The circle shows the change in the 3.0+
share between them._

Each bar splits the grade into five bands: 3.5+, 3.0 to 3.49, 2.5 to 2.99, 2.0
to 2.49, and below 2.0. The top bar uses grades already posted. The bottom bar
uses this year's current grades carried to June. Reading the two together tells
you whether this year is lifting the grade's cumulative GPA or pulling it down.

The circle on the right, **Change actual vs. projected**, is the difference in
the share at 3.0+. An up arrow in green means the projected share is higher than
the on-the-books share: this year's grades are helping.

This panel shows both bars whatever **GPA basis** is set to.

![Band mix for grade 9](screenshots/10-cgm-grade9-band-mix.png)

_Caption: The same panel with **Grade view** set to Grade 9 in the first weeks
of school. The top bar is entirely red._

> **Callout:** For grade 9 early in the year, the on-the-books bar reads 100%
> below 2.0. That is not a real result. Ninth graders have no earlier high
> school years, and almost no grades have posted yet, so there is nothing on the
> books. Read grade 9 from the projected bar only until first-quarter grades
> post.

### Band mix by grade

![Band mix by grade](screenshots/06-cgm-band-mix-by-grade.png)

_Caption: The same five bands, one bar per grade, for all four grades. Follows
the basis switch._

This chart does not change with **Grade view**. Use it to compare grades at a
glance. The label above the chart says which basis it is showing.

### Percent at 3.0+ by grade

![Percent at 3.0+ by grade](screenshots/07-cgm-pct-3-by-grade.png)

_Caption: One bar per grade with a grey tick at that grade's network goal. Green
means at or above goal._

The bar height follows **GPA basis**. The color is always projected, so a bar
can shrink below its tick when you switch to on the books and stay green,
because the grade is still projected to reach the goal. Hover a bar for the
goal, the gap, and how many more students are needed.

### Gap to goal, school by grade

![Gap to goal by school](screenshots/08-cgm-gap-by-school.png)

_Caption: One row per school and grade. The label is the gap to that school's
goal in percentage points._

This is where a school leader finds their own rows. Green rows are at or above
goal, red rows are below. The bar length is the share at 3.0+ on the chosen
basis; the label and color are always projected.

![Gap to goal for one school](screenshots/12-cgm-school-nca-gap-by-school.png)

_Caption: The same chart with **School** set to one school. The other schools
drop out; the goal ticks stay._

---

## 5. Find the students

### The Cusp Roster

Click **Show Cusp Roster** in the top right. A panel covers the charts.

![Cusp Roster open](screenshots/13-cgm-cusp-roster-open.png)

_Caption: The Cusp Roster for the grade chosen in **Grade view**. Names are
pixelated in this guide._

The roster lists every student in the selected grade whose projected cumulative
GPA is just under 3.0, between 2.75 and 2.99. These are the students a little
extra support could move over the line by June.

![Cusp Roster columns](screenshots/14-cgm-cusp-roster-panel.png)

_Caption: The roster columns. One row per student._

| Column                                 | What it means                                                                                                                                        |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Student Name**, **School**           |                                                                                                                                                      |
| **Reachable?**                         | Yes if the student can still reach a 3.0 cumulative this year. No if even the best possible grades this year would not get there.                    |
| **Student Slideback**                  | Yes if the student is projected to finish in a lower GPA band than they ended last year in.                                                          |
| **Cum Unweighted Actual**              | The cumulative GPA from grades already posted. On the books today.                                                                                   |
| **Cum Unweighted Projected**           | The cumulative GPA projected to June. This is the number that put the student on the list.                                                           |
| **Gap to 3.0**                         | 3.00 minus the projected GPA. How far the student is from the line.                                                                                  |
| **Min. GPA needed for cumulative 3.0** | The unweighted average the student needs across this year's courses to finish at 3.0. Above 4.33 is out of reach, which is what Reachable? No means. |

Hover a row for a short explanation of the last column.

To narrow the list, set **School** before opening the roster. To see a different
grade, change **Grade view**. Click **Hide Cusp Roster** to close it.

![Cusp Roster for one school](screenshots/15-cgm-cusp-roster-one-school.png)

_Caption: The roster with **School** set to one school._

> **Callout:** The roster is a projected list. A student appears because their
> year-end cumulative GPA is on course to land just under 3.0, not because their
> transcript reads that way today. As grades post, a few students will join or
> leave the list each week. That is normal.

### The Trends panel

Click **Show Trends** in the top right. A panel covers the charts with two
history views.

![Trends open](screenshots/16-cgm-trends-open.png)

_Caption: The Trends panel. A line chart on top, a band split below._

![Trend by grade](screenshots/17-cgm-trend-by-grade.png)

_Caption: One line per grade. Each point is the share of that grade that
finished that school year at a 3.0 cumulative or better._

Read a point like this: pick a year and a line. The grade 11 point at 2024 is
the share of juniors in 2023-24 who ended that year at 3.0+. Every year shown is
a closed year, so these are final numbers.

The lines are year-by-year snapshots, not the same students followed along. To
follow a class, read diagonally: grade 9 in 2022, grade 10 in 2023, grade 11 in
2024, grade 12 in 2025.

![Splay over time](screenshots/18-cgm-splay-over-time.png)

_Caption: The five-band split for the grade chosen in **Grade view**, one bar
per closed year._

The second chart shows the same five bands from the band mix charts, one bar per
closed year, for the grade in **Grade view**. **Region** and **School** apply to
both charts. Click **Hide Trends** to close the panel.

---

## Two walkthroughs

### Preparing for a Monthly Match Meeting

1. Open the tab. Leave **Academic Year** on this year and **GPA basis** on
   **Projected EOY**.
2. Set **Grade view** to Grade 11. Read the **At 3.0+ cumulative** tile and the
   goal row. That is the headline: where juniors stand against the goal, and how
   many more students it would take.
3. Read **Gap to goal, school by grade** for the grade 11 rows. Each school's
   gap is its own conversation.
4. Set **Grade view** to Grade 10 and repeat steps 2 and 3.
5. For grade 9, read the projected bar in the band mix panel and skip the
   on-the-books bar.

### Building a check-in list for juniors on the cusp

1. Set **Grade view** to Grade 11 and **School** to your school.
2. Click **Show Cusp Roster**.
3. Start with students marked **Reachable? Yes** and the smallest **Gap to
   3.0**. Those are the closest to the line.
4. Use **Min. GPA needed for cumulative 3.0** to set the ask: a student who
   needs a 3.4 this year needs mostly A's and B's from here.
5. Students marked **Reachable? No** cannot reach 3.0 this year. They still
   belong in a conversation about next year, but not on this list.

---

## Quick answers

**Why do the two charts on the right not change when I pick a grade?** They
always show all four grades for comparison. Only the tiles, the goal row, the
band mix, and the Cusp Roster follow **Grade view**.

**Why does grade 9 show 100% below 2.0 on the books?** Because almost nothing is
posted yet and freshmen have no earlier years. Read grade 9 from the projected
numbers until first-quarter grades post.

**Why did the tiles change but the goal row did not when I switched the basis?**
The goal row is always projected. Only the percentage tiles, the by-grade bars,
and the Cusp Roster values follow the switch.

**A student was on the Cusp Roster last week and is not this week.** The roster
is projected from current grades, which move as teachers post. Students join and
leave the list as their projection crosses 2.75 or 3.0.

**What does Reachable? No mean?** The unweighted average the student would need
across this year's courses is higher than the grade scale allows. A 3.0
cumulative is out of reach this year.

**Is this the same GPA as the Academic Health tabs?** No. Those tabs use the
weighted Y1 GPA, this year only. This tab uses the unweighted cumulative GPA,
all years. A student's cumulative number usually reads lower.

**Why is Paterson empty?** Paterson has no high school.

**When does it refresh?** Overnight, every day. The suite guide has the
schedule.

---

## Glossary

| Term                      | Meaning                                                                               |
| ------------------------- | ------------------------------------------------------------------------------------- |
| **Cumulative GPA**        | GPA across every high school year completed so far, plus this one.                    |
| **Unweighted**            | Every course counts the same regardless of level. The transcript GPA.                 |
| **Projected EOY**         | The cumulative GPA if this year's current grades hold to the end of the year.         |
| **On the books today**    | The cumulative GPA from grades already posted.                                        |
| **GPA band**              | 3.5+, 3.0 to 3.49, 2.5 to 2.99, 2.0 to 2.49, below 2.0.                               |
| **Cusp**                  | A projected cumulative GPA between 2.75 and 2.99.                                     |
| **Reachable**             | Whether a 3.0 cumulative can still be reached this year with grades the scale allows. |
| **Slideback**             | Projected to finish in a lower band than the student ended last year in.              |
| **Gap to goal**           | Projected share at 3.0+ minus the goal, in percentage points.                         |
| **Students still needed** | How many more students at 3.0+ would meet the goal.                                   |

---

## Screenshot manifest

Files live in `screenshots/`. Rendered on September 11, 2026 from the
documentation copy of the workbook. Student names are pixelated in 13, 14,
and 15.

| File                                  | Shows                                      |
| ------------------------------------- | ------------------------------------------ |
| `01-cgm-full.png`                     | Whole tab, defaults                        |
| `02-cgm-header-controls.png`          | Title strip and controls                   |
| `03-cgm-four-tiles.png`               | Four tiles                                 |
| `04-cgm-goal-row.png`                 | Goal row                                   |
| `05-cgm-band-mix-network.png`         | Band mix with change glyph                 |
| `06-cgm-band-mix-by-grade.png`        | Band mix by grade                          |
| `07-cgm-pct-3-by-grade.png`           | Percent at 3.0+ by grade                   |
| `08-cgm-gap-by-school.png`            | Gap to goal by school and grade            |
| `10-cgm-grade9-band-mix.png`          | Grade 9 band mix, on-the-books bar all red |
| `12-cgm-school-nca-gap-by-school.png` | Gap chart filtered to one school           |
| `13-cgm-cusp-roster-open.png`         | Cusp Roster over the tab                   |
| `14-cgm-cusp-roster-panel.png`        | Cusp Roster columns                        |
| `15-cgm-cusp-roster-one-school.png`   | Cusp Roster, one school                    |
| `16-cgm-trends-open.png`              | Trends panel over the tab                  |
| `17-cgm-trend-by-grade.png`           | Trend by grade                             |
| `18-cgm-splay-over-time.png`          | Splay over time                            |
