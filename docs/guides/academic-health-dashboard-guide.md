# Academic Health Dashboard Guide

School Year 2026-27. For school leaders, assistant principals, grade level
chairs, and teachers in Newark, Camden, and Paterson middle and high schools.

Notes for the designer: build this as a Zendesk Guide article using the KIPP NJ
| Miami Zendesk snippets (`design_system/kippnj-miami-design/zendesk/`, read its
README first). Lines beginning `> **Callout:**` are callouts; drop the word
"Callout:" when rendering and use the Note style unless the text warns about a
mistake, then use Warning. Italic lines beginning "Caption:" directly under an
image are that image's caption; drop the word "Caption:". Image references point
at `screenshots/` next to this file; upload each to Guide media and swap the
path for the hosted URL, keeping the order in the manifest at the end. Put a
table of contents after "What this dashboard does", linking to the two role
sections, the three walkthroughs, Quick answers, and the Glossary. Numbered
lists are step sequences; keep the markdown tables as tables. Names and student
numbers are already pixelated in every image that had them; do not re-crop. The
DeansList import guide is already linked in the text. The screenshot manifest is
a production note, not reader content. On-screen control names appear in bold
exactly as the dashboard shows them.

---

## What this dashboard does

The Academic Health dashboard shows how students are doing on grades and GPA
this year. It lives in Tableau, in the **Academic & Gradebook Health Suite**
workbook, on two tabs:

- **Academic Health Home**: the network and school view. Nine headline numbers,
  one bar per school, course failures by subject, and progress against the GPA
  goals.
- **Academic Health Schools**: one school at a time. GPA distribution by grade,
  letter grades by teacher, student rosters, and the Office Hours list with its
  DeansList export.

Open it here:
<https://tableau.kipp.org/t/KIPPNJ/views/AcademicGradebookHealthSuite/AcademicHealthHome>

The same workbook holds the **Gradebook School Rollup** and **Gradebook Teacher
View** tabs, which are about whether teachers' gradebooks are in good shape.
Those have their own guide, the
[Gradebook Health Dashboard Guide](https://teamschools.zendesk.com/hc/en-us/articles/43377104764567-Gradebook-Health-Dashboard-Guide).
This guide covers the two Academic Health tabs and the **Landing Page** that
links them.

> **Callout:** Elementary schools and Miami are not on this dashboard. Paterson
> appears for middle school only. Cumulative GPA columns are high school only.

---

## Before you start

### When the data updates

Both tabs refresh once a day, overnight. The title strip on each tab prints the
exact time in Pacific time, three hours behind our schools. A stamp of 6:36 AM
PST means 9:36 AM Eastern. If the stamp is from this morning, you are looking at
grades entered through yesterday.

> **Callout:** Entered today, visible tomorrow. A grade a teacher posts this
> afternoon shows up on the dashboard tomorrow morning.

### The two GPAs

Every GPA number on these two tabs is the **Y1 GPA**: this year only, weighted,
running from the start of the year to today. Weighted means an honors or AP
course earns more grade points than a regular course for the same letter, so an
A in AP Biology lifts the GPA more than an A in Biology. This is the GPA the 3.0
and 2.0 goals are set against.

The rosters also carry a **cumulative unweighted GPA**, which covers every high
school year on record and scores every course on the same scale, topping out at
an A+. This is the number colleges see on a transcript and the one that drives
college matriculation, so it matters most for juniors and seniors. A student's
cumulative number usually reads lower than their Y1 number. That is expected.
The **Cumulative GPA Monitor** tab is built around the cumulative number and has
its own guide.

### The Marking Period control

This is the control people will ask about all year, so read this section even if
you skip the rest.

Every row of data behind these tabs belongs to one term: **Q1**, **Q2**, **Q3**,
**Q4**, or **Y1**. Y1 is a real row in the data, not a total Tableau adds up.
The **Marking Period** dropdown picks which term the tabs read. Nothing is
combined across terms.

What a term shows:

| You pick      | Course grades and letter bands show           | GPA numbers show                         |
| ------------- | --------------------------------------------- | ---------------------------------------- |
| **Y1**        | The running year-to-date grade in each course | Y1 GPA as of today                       |
| **Q1**–**Q4** | That quarter's grade only                     | Y1 GPA **as of the end of that quarter** |

So the GPA side of the dashboard is always a year number, whichever term you
pick. The course-grade side switches to a single quarter when you pick one.

What that means during the year:

- **While Q1 is in progress**, Q1 and Y1 show the same numbers. There is only
  one quarter of grades, so the running year grade and the quarter grade are
  identical. Switching between them changes nothing you will notice.
- **Once Q1 closes and Q2 begins**, Q1 freezes at the stored quarter grade. Y1
  keeps moving as Q2 grades post. Picking Q2 shows only Q2 gradebook grades on
  the teacher chart and the rosters, while the GPA distribution above them still
  shows the running year GPA. This is the moment a Q2 view shows a quarter
  letter grade sitting next to a year GPA.
- **On the Home tab**, the nine tiles and the school bars read the Y1 GPA as of
  the chosen term. The course-failures heatmap always tests the year-to-date
  letter grade. The goal panel ignores the control entirely and says so in its
  subtitle.

> **Callout:** Leave **Marking Period** on **Y1** unless you need to see how a
> single closed quarter ended. Y1 is the default and is what the goals are set
> against.

### The Academic Year control

**Academic Year** switches between this year and last year. Last year is useful
for distributions and failure rates. It is not useful for rosters: the
points-needed columns, the week-over-week change lines, the cumulative GPA
columns, and the lowest-category column are all blank or read "not available" on
a closed year, because they only exist for the year in progress.

### The GPA Roster links

The header of each tab has three links, **Newark**, **Camden**, and
**Paterson**, that open a Google Sheet for that region. Each sheet has one row
per enrolled student with the four quarter GPAs side by side, the Y1 GPA, the
cumulative GPA (unweighted, weighted, and projected), the student's advisory in
the `team` column, ADA, and IEP and 504 status. The sheets refresh nightly on
the same schedule as the dashboard. Use one when you need the whole region in a
spreadsheet rather than one school on screen.

---

## For regional and school leaders: Academic Health Home

![Home overview](screenshots/01-home-full.png)

_Caption: The Home tab at network scope. Controls across the top, nine tiles,
school bars on the left, course failures and the goal panel on the right._

### 1. Set your controls

![Home header controls](screenshots/02-home-header-controls.png)

_Caption: The control strip. Region and Marking Period are single-choice. Head
of School and School Level accept more than one value._

| Control                 | What it does                                                                                 |
| ----------------------- | -------------------------------------------------------------------------------------------- |
| **Academic Year**       | This year or last year. Reaches everything on the tab.                                       |
| **Region**              | All, Newark, Camden, or Paterson. Reaches everything, including the goal panel.              |
| **Marking Period**      | Q1 through Q4, or Y1. See above. Does not reach the goal panel.                              |
| **Head of School**      | Narrows the tiles, bars, and heatmap to one leader's schools. Does not reach the goal panel. |
| **School Level**        | MS or HS. Same reach as Head of School.                                                      |
| **Special Populations** | IEP, MLL, 504, or G&T. Sits beside the school bars and changes only that chart.              |

![Home with Region set to Newark](screenshots/08-home-region-newark-full.png)

_Caption: The same tab with **Region** set to Newark. Camden and Paterson drop
from every panel. The goal panel keeps the network rows in its summary table
because network totals have no region._

### 2. Read the nine tiles

![The nine tiles](screenshots/03-home-ban-tiles.png)

_Caption: Three tiles each for Network, Middle Schools, and High Schools._

Each group has the same three numbers:

| Tile               | What it counts                                                                          |
| ------------------ | --------------------------------------------------------------------------------------- |
| **% At/Above 3.0** | Students with a Y1 GPA of 3.00 or higher, out of students who have a Y1 GPA.            |
| **% Below 2.0**    | Students with a Y1 GPA under 2.00, out of the same group.                               |
| **% Failing 2+**   | Students failing two or more courses right now, out of students with any graded course. |

Under the big number, a line reads "vs. 1 wk" and another "vs. 2 wks". These are
the change in percentage points since one and two weeks ago, for the same
students. A change line is blank when fewer than 80% of the students in that
tile have gradebook history reaching back that far. Early in the year most lines
are blank, and they fill in as the weeks pass. Hover a tile to see the counts
behind the percentage and how much history it has.

> **Callout:** A blank change line is not an error. It means the tile does not
> yet have enough weeks of history to compare against. It will appear on its
> own.

![The tiles with Academic Year set to last year](screenshots/09-home-ban-tiles-prior-year.png)

_Caption: Last year's tiles. The change lines are blank because week-over-week
history only exists for the year in progress._

### 3. Read the school bars

![School bars with Special Populations set to IEP](screenshots/04-home-school-bars-iep.png)

_Caption: One bar per school, grouped by region. The blue bar is all students.
The grey bar is the selected population, with its own label._

The blue bar is the share of students at or above a 3.0 Y1 GPA. The grey bar
underneath is the same share for the group chosen in **Special Populations**,
labeled with the group and its percentage.

When **Special Populations** is IEP, a check mark or an X follows the label. A
check mark means the gap between students without an IEP and students with one
is 10 percentage points or less. An X means the gap is wider than that. No mark
appears when the school has fewer than 10 students with an IEP, because the
number would not be reliable.

Hover a bar for the exact figures: the all-students rate, the population's rate,
and the gap stated two ways. "Gap vs. all students" compares the group to the
whole school, which includes the group itself. "Gap vs. non-IEP" compares the
group to everyone else and reads larger. Use the second one when you are asked
about the differential.

![School bar tooltip with IEP selected](screenshots/30-user-tooltip-school-bar-iep-gaps.png)

_Caption: Hovering a school bar. Both gap figures are listed, with a note on why
they differ._

![School bars with Special Populations set to MLL](screenshots/05-home-school-bars-mll.png)

_Caption: The same chart with **Special Populations** set to MLL. Only the grey
bars and labels change._

Click any school bar to open that school on the Schools tab.

### 4. Read the course failures heatmap

![Course failures by school heatmap](screenshots/06-home-course-failures-heatmap.png)

_Caption: One row per school, one column per core subject. Darker red means a
higher share of students failing._

Each cell is the share of students at that school who are failing at least one
course in that subject, based on the year-to-date letter grade. Only the four
core subjects appear: ELA, Math, Science, and Social Studies.

Hover a cell for a breakdown by grade level.

![Heatmap tooltip with grade-level breakdown](screenshots/29-user-tooltip-heatmap-grade-breakdown.png)

_Caption: Hovering a heatmap cell. The small chart shows the failure rate for
each grade in that school and subject._

Click a cell to open that school on the Schools tab with **Credit Type** set to
that subject. The teacher chart there will show only teachers of that subject.

> **Callout:** After clicking a heatmap cell, the Schools tab's **Credit Type**
> control is set for you. Clear it if you want to see every teacher at the
> school.

### 5. Read the goal panel

![Goal panel](screenshots/07-home-goal-panel.png)

_Caption: Goal versus actual for each high school and grade, with a summary
table of network rows below._

The bars show the share of students at or above a 3.0 weighted Y1 GPA for each
high school and grade, against that school's goal. A tick marks the goal. The
label is the gap in percentage points. Green means at or above goal. Red means
below.

The table under it repeats the network rows: goal rate, actual rate, gap,
students measured, and students enrolled in the grade.

Two things to know:

- The panel covers grades 9, 10, and 11. Grade 12 has no Y1 GPA goal on record
  this year. Middle schools have no goals in this panel.
- The panel does not respond to **Marking Period**, because goals are set for
  the year.

Hover any bar for the goal, the actual, the gap, and how many students met it.

### 6. Go to the Schools tab

Clicking a school bar or a heatmap cell opens the **Academic Health Schools**
tab filtered to that school. You can also open the Schools tab directly and pick
the school from its **School** dropdown.

---

## For school leaders, APs, and grade level chairs: Academic Health Schools

![Schools tab default](screenshots/11-schools-full-default.png)

_Caption: The Schools tab with **School** set to All. The GPA distribution by
grade on top, letter grades by teacher below. Set a school first._

> **Callout:** The tab opens with **School** set to All, which lists every
> teacher in the network. Pick your school before you read anything.

### 1. Set your controls

![Schools header controls](screenshots/12-schools-header-controls.png)

_Caption: The control strip with **School** set to one school._

| Control            | What it does                                                                                                                                          |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Academic Year**  | This year or last year.                                                                                                                               |
| **Marking Period** | Q1 through Q4, or Y1. See "Before you start".                                                                                                         |
| **School**         | One or more schools. Set this first.                                                                                                                  |
| **Manager**        | Narrows to teachers who report to that manager. Also narrows the GPA distribution to those teachers' students, so use it with the teacher chart only. |
| **Grade Level**    | One or more grades.                                                                                                                                   |
| **Y1 Cusp Band**   | Near 3.0 (2.70–2.99), Near 2.0 (1.70–1.99), or Not on Cusp. See the callout below.                                                                    |
| **IEP**            | Students with or without an IEP.                                                                                                                      |
| **ADA 80%+**       | Students at or above 80% attendance, below it, or with no attendance data yet.                                                                        |
| **Credit Type**    | Subject code. ENG, MATH, SCI, SOC, and the electives. Set for you when you click a heatmap cell on Home.                                              |

![Marking Period dropdown open](screenshots/33-user-marking-period-dropdown.png)

_Caption: The **Marking Period** choices. Y1 is the default._

![Y1 Cusp Band dropdown open](screenshots/34-user-cusp-band-dropdown.png)

_Caption: The **Y1 Cusp Band** choices. "Not on Cusp" is every student outside
the two bands._

> **Callout:** **Y1 Cusp Band** reaches every panel on the tab, including the
> GPA distribution. Pick "Near 3.0" and the distribution collapses to one band
> and the "% ≥ 3.0" column reads 0%, because every student left is below 3.0.
> That is the filter doing its job. Use the cusp band for the rosters and the
> teacher chart, then set it back to All to read the distribution.

![Cusp band filter collapsing the distribution](screenshots/16-schools-cusp-band-filter-collapse.png)

_Caption: The distribution with **Y1 Cusp Band** set to Near 3.0. Every bar is
one band and "% ≥ 3.0" reads 0%. Expected._

### 2. Read the GPA distribution

![GPA distribution and % ≥ 3.0](screenshots/13-schools-gpa-distribution.png)

_Caption: One bar per grade, plus an All Grades bar. Each bar is split into five
GPA bands. The column on the right is the share at or above 3.0._

Each bar is 100% of the students in that grade who have a Y1 GPA, split into
five bands:

| Band      | Y1 GPA        |
| --------- | ------------- |
| 3.5+      | 3.50 or above |
| 3.0–3.49  | 3.00 to 3.49  |
| 2.5–2.99  | 2.50 to 2.99  |
| 2.0–2.49  | 2.00 to 2.49  |
| Below 2.0 | Under 2.00    |

The "% ≥ 3.0" column adds the first two bands. This chart reads the year GPA
whatever **Marking Period** says, so it is the same picture at Q1 and at Y1.

Hover a segment for the student count.

### 3. Click a band to see the students

Click any segment. The other segments dim, and a panel titled **Students in the
selected band** opens below the distribution.

![Band click with the roster panel open](screenshots/26-user-band-click-roster.png)

_Caption: The Below 2.0 segment for grade 10 is selected. The panel lists those
students, one row per course. Names are pixelated in this guide._

The roster has one row per student and course. Columns, left to right:

| Column                           | What it is                                                                                                                                   |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Student Name**                 |                                                                                                                                              |
| **Course - Section**             | Course name and section or period.                                                                                                           |
| **Teacher Name**                 |                                                                                                                                              |
| **Gpa Y1**                       | The student's Y1 GPA. Same on every row for that student.                                                                                    |
| **Y1 Cusp Band**                 | Near 3.0, Near 2.0, or Not on Cusp.                                                                                                          |
| **Y1 % Grade (Running)**         | Year-to-date percent in this course as of the selected term.                                                                                 |
| **Y1 Letter Grade (Running)**    | The letter for that percent.                                                                                                                 |
| **Category Driving Gap (label)** | The gradebook category with the lowest percent in this course, and that percent. "not available" when the course has no category grades yet. |
| **% Needed Next Grade**          | The percent the student needs this term for the course to reach the next letter grade.                                                       |
| **% Need 80**                    | The percent the student needs this term for the course to reach an 80.                                                                       |
| **Cum. Y1 GPA Unweighted**       | Cumulative unweighted GPA from posted grades. High school only.                                                                              |
| **Cum. Y1 GPA Unweighted Proj.** | Cumulative unweighted GPA projected to year end. High school only.                                                                           |
| **Cum. Band Change**             | Projected cumulative band minus last year's band. Negative means sliding.                                                                    |
| **Cum 3.0 Possible?**            | Yes or No: whether a 3.0 cumulative is still reachable this year.                                                                            |
| **Y1 GPA Needed For Cum. 3.0**   | The unweighted average the student needs across this year's courses to finish at a 3.0 cumulative.                                           |

Some cells read "Null". That is normal in three cases: the course has no posted
grade yet, the student is already at the top letter grade so there is no next
grade to reach, or the student is in middle school and has no cumulative GPA.

> **Callout:** "% Needed Next Grade" and "% Need 80" can be above 100 or
> below 0. Above 100 means the next grade is out of reach this term. Below 0
> means it is already secured. Read them as "how hard is this," not as a literal
> score.

To export the roster, click **Download - Choose "Y1 Schools - GPA export"** at
the top of the panel. In the dialog, keep **Y1 Schools - GPA export** checked,
pick Excel or CSV, and click **Download**. The export is one row per student
with the GPA and cumulative columns, not one row per course.

![Download dialog for the GPA export](screenshots/31-user-download-dialog-gpa-export.png)

_Caption: The Download Crosstab dialog. The export sheet is already checked._

Click the X in the panel header to close it.

### 4. Read the letter grades by teacher

![Letter grade distribution by teacher](screenshots/14-schools-teacher-distribution.png)

_Caption: The School row on top is the reference. Below it, one bar per teacher,
worst failure rate first._

Each bar is 100% of a teacher's graded course enrollments, split by letter:

| Band          | Meaning                            |
| ------------- | ---------------------------------- |
| A, B, C, D, F | First letter of the course grade.  |
| (None)        | Enrolled, but no grade posted yet. |

Teachers are sorted by their failure rate, highest first. The **School** row at
the top shows the same split for the whole school so you can compare. Homeroom
and study hall are left out.

This is the panel that follows **Marking Period**. On Y1 the letters are
year-to-date. On a quarter they are that quarter's letters.

Hover a bar for the numbers: how many enrollments, the share at A/B/C, the share
at D/F, the failure rate, and the gradebook category with the lowest average
across that teacher's courses.

![Teacher bar tooltip](screenshots/28-user-tooltip-teacher-bar.png)

_Caption: Hovering a teacher's bar. The failure rate here is exact; the bar
label is rounded._

### 5. Click a teacher's bar to see their students

Click any segment of a teacher's bar. The chart narrows to the left half of the
screen and a roster appears on the right with that teacher's students who hold
that letter grade, one row per student.

![Teacher bar clicked with the roster on the right](screenshots/27-user-teacher-bar-click-popout.png)

_Caption: A teacher's D segment is selected. The roster on the right lists the
students earning a D in that teacher's sections. Names are pixelated in this
guide._

The roster has the same columns as the band roster in step 3. Click the same
segment again to clear the selection and restore the chart.

> **Callout:** Click one segment, not the teacher's name. The letter band you
> click is the one the roster shows.

### 6. Build the Office Hours roster

Click **Show Office Hours** in the top right. A panel covers the tab.

![Office Hours panel open](screenshots/19-schools-office-hours-open-full.png)

_Caption: The Office Hours roster for one school. The header shows how many rows
and students are listed. Names are pixelated in this guide._

Who is on the list:

- Every course a student is **failing**, for every student.
- Every course, failing or not, for every student in the **Near 3.0** band (Y1
  GPA 2.70 to 2.99).

So a student failing one course appears once. A student near 3.0 appears once
per course, with their weakest course first. Students below 2.0 who are not
failing anything do not appear.

![Office Hours roster detail](screenshots/20-schools-office-hours-roster.png)

_Caption: The roster. One row per student and course, weakest course first
within each student._

Columns, left to right:

| Column                                         | What it is                                                                                                                                                                                                     |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **School**                                     |                                                                                                                                                                                                                |
| **Student Name**                               |                                                                                                                                                                                                                |
| **Grade Level**                                |                                                                                                                                                                                                                |
| **Y1 Cusp Band**                               | Near 3.0, Near 2.0, or Not on Cusp.                                                                                                                                                                            |
| **Teacher Priority**                           | 1 is the student's lowest course grade, 2 the next lowest, and so on. Courses with no grade yet are not ranked.                                                                                                |
| **Course Name**, **Section**, **Teacher Name** |                                                                                                                                                                                                                |
| **Row Type**                                   | Failing - cusp, Failing, or Cusp improvement. Also the row color.                                                                                                                                              |
| **Y1 GPA**                                     |                                                                                                                                                                                                                |
| **Grade %** and **Ltr**                        | The course percent and letter for the selected term.                                                                                                                                                           |
| **Pts to Next**                                | "+7 to 83%" means seven more points in this course reaches the next letter, which starts at 83. "+4 to passing" means four points reaches a 60. "top band" means the student is already at the highest letter. |
| **Category Driving Gap**                       | The gradebook category pulling this course down, with its percent.                                                                                                                                             |

The row colors come from **Row Type**: red for a failing course, blue for a
course a Near 3.0 student could improve, and a darker red for a failing course
belonging to a student who is also on the cusp.

The roster follows every control above it. Set **School** and **Grade Level**
first. Use **Y1 Cusp Band** to see only the Near 3.0 rows. Use **Credit Type**
to see one department's rows.

> **Callout:** The list rebuilds every night from current grades. There is no
> saved or frozen version. If you want to keep this week's list, export it (next
> step). The DeansList export stamps each row with the Monday of the week it was
> pulled.

Click **Hide Office Hours** to put the panel away.

### 7. Export the roster for DeansList

Inside the Office Hours panel, click **Show DeansList**. A second panel opens
over the roster.

![DeansList panel open](screenshots/22-schools-deanslist-panel.png)

_Caption: The DeansList export panel over the Office Hours roster. Names and
student numbers are pixelated in this guide._

The panel has three parts:

1. **Sessions**: Top 2, Top 4, or all. This caps how many courses per student go
   into the export, using the priority rank. Top 2 sends each student to their
   two lowest-graded teachers. Top 4 sends them to four. Pick the number of
   Office Hours sessions a student can attend in the cycle.
2. **Download Roster - Select "Y1 - DeansList Export"**: opens Tableau's
   Download Crosstab dialog. Keep **Y1 - DeansList Export** checked, choose CSV
   or Excel, and click **Download**. Ignore the other sheet listed in the
   dialog.
3. The export preview: one row per student and course, with these columns.

| Column                                | What it is                                                                                    |
| ------------------------------------- | --------------------------------------------------------------------------------------------- |
| **Student Name (DELETE THIS COLUMN)** | For checking the file. Delete it before importing to DeansList.                               |
| **Student Number**                    | The DeansList match key.                                                                      |
| **Roster Name**                       | "Office Hours - First Last", the teacher the student should attend.                           |
| **Roster Notes**                      | Course, section, the lowest gradebook category, and "Week of" the Monday the file was pulled. |

![DeansList panel with Sessions set to Top 4](screenshots/24-schools-deanslist-sessions4.png)

_Caption: The same export with **Sessions** set to Top 4. Each student now
appears on up to four rosters._

![Download dialog for the DeansList export](screenshots/32-user-download-dialog-deanslist-export.png)

_Caption: The Download Crosstab dialog. Keep **Y1 - DeansList Export** checked._

Then follow
[Importing Office Hours Rosters into DeansList](https://teamschools.zendesk.com/hc/en-us/articles/43411553089047-Importing-Office-Hours-Rosters-into-DeansList)
to load the file. The **DeansList import** text at the top of the panel links to
the same article.

> **Callout:** Set **School**, **Grade Level**, and **Sessions** before you
> download. The export matches what is on screen, including any cusp band or
> subject filter you have set.

### 8. Subscribe

Tableau can email you either tab on a schedule. Set your controls, click **Save
Custom View** in the bottom toolbar and name it, then click **Watch** and choose
**Subscriptions**. Pick a format and a frequency. The Gradebook Health Dashboard
Guide has the full steps with pictures; they are the same here.

> **Callout:** A subscription sends the view as saved. Save a custom view with
> your school and **Marking Period** set, and re-save it when the quarter
> changes.

---

## Three walkthroughs

### A grade level chair's Wednesday

1. Open the Schools tab. Set **School** and **Grade Level**.
2. Set **Y1 Cusp Band** to Near 3.0. Read the teacher chart to see where the
   cusp students' low grades sit.
3. Set **Y1 Cusp Band** back to All. Click **Show Office Hours**.
4. Read the roster. Each student's weakest course is priority 1. **Pts to Next**
   is the ask for that course.
5. Click **Show DeansList**, set **Sessions**, and download. Delete the name
   column and import to DeansList.

### An AP of Instruction's Monday

1. Open the Home tab. Read the **% Failing 2+** tiles and the heatmap. Find the
   darkest cells.
2. Click a dark cell. The Schools tab opens on that school and subject.
3. Read the teacher chart. The teachers with the highest failure rate are on
   top. Hover for the exact rate and the category dragging it down.
4. Click a teacher's F segment. The roster on the right names the students.
5. Clear **Credit Type** to see the rest of the school.

### A teacher's ten minutes

1. Open the Schools tab. Set **School** to yours.
2. Find your name on the teacher chart. Compare your bar to the **School** row
   above.
3. Click your D or F segment. The roster on the right lists the students and
   what each one needs to reach the next grade.
4. Click **Show Office Hours** and set **Y1 Cusp Band** to Near 3.0 to see which
   of your students are within reach of a 3.0 and what your course would need
   from them.

---

## Quick answers

**I changed Marking Period to Q1 and nothing changed.** While Q1 is in progress,
Q1 and Y1 are the same grades. Differences appear once Q1 closes.

**I picked Q2 and the GPA distribution did not change but the teacher chart
did.** Correct. The distribution reads the year GPA at every setting. The
teacher chart and rosters read the quarter you picked.

**The cusp band filter made the distribution collapse.** It reaches every panel.
Set it back to All to read the distribution.

**A tile's change line is blank.** Not enough students have gradebook history
that far back yet. It fills in on its own.

**A student is on the Office Hours list but not on the cusp.** They are failing
a course. Failing courses are listed for every student.

**A student near 2.0 is not on the Office Hours list.** The list includes Near
3.0 students and any student failing a course. A Near 2.0 student who is passing
everything is not listed.

**"% Needed Next Grade" reads Null.** The student has no posted grade in that
course, or is already at the top letter grade.

**Pts to Next reads "top band".** The student is at the highest letter grade in
that course.

**Cumulative columns are blank for my students.** Cumulative GPA is high school
only.

**The teacher chart shows a (None) band.** Those students are enrolled but have
no posted grade yet.

**The heatmap says one thing and the teacher chart another.** The heatmap tests
the year-to-date letter grade and counts students. The teacher chart tests the
letter for the selected term and counts course enrollments.

**Where is my school's goal?** The goal panel on Home covers high school grades
9, 10, and 11. Grade 12 and middle school have no Y1 GPA goal this year.

**Where do I set who is on the Office Hours list?** The rules are fixed: failing
courses plus Near 3.0 students. The one setting is **Sessions**, which caps
courses per student in the DeansList export.

---

## Glossary

| Term                     | Meaning                                                                                                                   |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| **Y1 GPA**               | This year's weighted GPA, running from the start of the year. The GPA behind every tile and chart on these tabs.          |
| **Cumulative GPA**       | Unweighted GPA across every high school year on record. Appears on rosters and on the Cumulative GPA Monitor tab.         |
| **Projected**            | The cumulative GPA if this year's in-progress grades hold to year end.                                                    |
| **Marking Period**       | The term the tabs read: Q1 to Q4, or Y1 for the running year.                                                             |
| **GPA band**             | The five Y1 GPA ranges on the distribution: 3.5+, 3.0–3.49, 2.5–2.99, 2.0–2.49, Below 2.0.                                |
| **Cusp band**            | Near 3.0 is a Y1 GPA of 2.70 to 2.99. Near 2.0 is 1.70 to 1.99.                                                           |
| **Letter band**          | The first letter of a course grade: A, B, C, D, F. (None) is enrolled with no grade posted.                               |
| **Failing 2+**           | A student with a failing year-to-date grade in two or more courses.                                                       |
| **Category Driving Gap** | The gradebook category (Formative Mastery, Summative Mastery, Homework, Work Habits) with the lowest percent in a course. |
| **% Needed Next Grade**  | The percent a student needs this term for the course's year-to-date grade to reach the next letter.                       |
| **% Need 80**            | The same, for reaching an 80.                                                                                             |
| **Pts to Next**          | Points between the course percent and the next letter's cutoff, and what that cutoff is.                                  |
| **Teacher Priority**     | Rank of a student's courses by percent grade, lowest first. Drives the Office Hours order and the Sessions cap.           |
| **Cum 3.0 Possible?**    | Whether a 3.0 cumulative unweighted GPA is still reachable by year end.                                                   |
| **Cum. Band Change**     | Projected cumulative band minus last year's band. Negative means sliding.                                                 |
| **Sessions**             | The Office Hours export cap: Top 2, Top 4, or all courses per student.                                                    |
| **Special Populations**  | IEP, MLL, 504, or G&T. Changes only the grey bars on Home.                                                                |

---

## Screenshot manifest

Files live in `screenshots/`. Images 01 to 25 were rendered from the production
dashboard on September 11, 2026; images 26 and up were captured in a browser the
same day. Student names and student numbers are pixelated in every image that
shows them. Teacher names are visible.

| File                                           | Shows                                            |
| ---------------------------------------------- | ------------------------------------------------ |
| `01-home-full.png`                             | Home overview                                    |
| `02-home-header-controls.png`                  | Home header controls                             |
| `08-home-region-newark-full.png`               | Home with Region set to Newark                   |
| `03-home-ban-tiles.png`                        | The nine tiles                                   |
| `09-home-ban-tiles-prior-year.png`             | The tiles with Academic Year set to last year    |
| `04-home-school-bars-iep.png`                  | School bars with Special Populations set to IEP  |
| `30-user-tooltip-school-bar-iep-gaps.png`      | School bar tooltip with IEP selected             |
| `05-home-school-bars-mll.png`                  | School bars with Special Populations set to MLL  |
| `06-home-course-failures-heatmap.png`          | Course failures by school heatmap                |
| `29-user-tooltip-heatmap-grade-breakdown.png`  | Heatmap tooltip with grade-level breakdown       |
| `07-home-goal-panel.png`                       | Goal panel                                       |
| `11-schools-full-default.png`                  | Schools tab default                              |
| `12-schools-header-controls.png`               | Schools header controls                          |
| `33-user-marking-period-dropdown.png`          | Marking Period dropdown open                     |
| `34-user-cusp-band-dropdown.png`               | Y1 Cusp Band dropdown open                       |
| `16-schools-cusp-band-filter-collapse.png`     | Cusp band filter collapsing the distribution     |
| `13-schools-gpa-distribution.png`              | GPA distribution and % ≥ 3.0                     |
| `26-user-band-click-roster.png`                | Band click with the roster panel open            |
| `31-user-download-dialog-gpa-export.png`       | Download dialog for the GPA export               |
| `14-schools-teacher-distribution.png`          | Letter grade distribution by teacher             |
| `28-user-tooltip-teacher-bar.png`              | Teacher bar tooltip                              |
| `27-user-teacher-bar-click-popout.png`         | Teacher bar clicked with the roster on the right |
| `19-schools-office-hours-open-full.png`        | Office Hours panel open                          |
| `20-schools-office-hours-roster.png`           | Office Hours roster detail                       |
| `22-schools-deanslist-panel.png`               | DeansList panel open                             |
| `24-schools-deanslist-sessions4.png`           | DeansList panel with Sessions set to Top 4       |
| `32-user-download-dialog-deanslist-export.png` | Download dialog for the DeansList export         |
