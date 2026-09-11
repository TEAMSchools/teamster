# Academic & Gradebook Health Suite

School Year 2026-27. The home guide for the suite. Start here, then open the
guide for the tab you use.

Notes for the designer: build this as a Zendesk Guide article using the KIPP NJ
| Miami Zendesk snippets (`design_system/kippnj-miami-design/zendesk/`, read its
README first). Lines beginning `> **Callout:**` are callouts; drop the word
"Callout:" when rendering. The italic line beginning "Caption:" under the image
is its caption; drop the word "Caption:". The image reference points at
`screenshots/`; upload it to Guide media and swap in the hosted URL. This
article is short; no table of contents. The screenshot manifest is a production
note, not reader content.

Prompt for Claude Design (paste as-is, with this file attached):

```text
Build a short Zendesk Guide help-center article from the attached Markdown
file, "Academic & Gradebook Health Suite", using the KIPP NJ | Miami Zendesk
article subsystem in design_system/kippnj-miami-design/zendesk/. Read that
folder's README.md first and follow its rules exactly: tables with inline
styles and literal hex, no <style>, no var(), no flex or grid, margin only on
<table>, <div> not <p> inside cells, system font stack, weights 400, 600 and
700 only. Use the snippets in index.html. Do not repeat the title; Zendesk
renders it. No table of contents. A line beginning "> **Callout:**" is a Note
callout; drop the word "Callout:". The italic "Caption:" line under the image
is its caption; drop the word "Caption:". Keep the two tables as tables. Keep
every link live. Leave out the designer notes, this prompt, and the screenshot
manifest. Keep the wording; do not paraphrase or add emoji. Output one HTML
file ready to paste into the Zendesk article body.
```

---

## What the suite is

The Academic & Gradebook Health Suite is one Tableau workbook that answers two
questions for middle and high schools in Newark, Camden, and Paterson: how are
students doing on grades and GPA, and are teachers' gradebooks in good shape.

It has five working tabs and a Landing Page that ties them together. Each tab
has its own guide, linked below.

Open the suite here:
<https://tableau.kipp.org/t/KIPPNJ/views/AcademicGradebookHealthSuite/LandingPage?:embed=y>

> **Callout:** Elementary schools and Miami are not on the suite yet. Paterson
> appears for middle school only.

## The Landing Page

![Landing Page](screenshots/00-landing-page.png)

_Caption: The Landing Page. Four headline tiles across the top with a region
breakdown under each, one card per tab in the middle with its help guide link,
and a glossary and coverage table at the bottom._

The four tiles are the suite's headline numbers: the share of students at or
above a 3.0 weighted Y1 GPA, the share failing two or more courses, the share of
grade 11 at or above a 3.0 unweighted cumulative GPA, and the share of teachers
with a healthy gradebook. Each tile prints when its data last updated.

The cards in the middle say what each tab is for, who it is built for, and
whether it shows student names. Click a card title to open the tab, or its help
guide link to open the guide.

## The tabs and their guides

| Tab                         | What it answers                                                                                            | Guide                                                                                                                                             |
| --------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Academic Health Home**    | How is this year's weighted GPA and course-failure picture moving, by school and subject?                  | [Academic Health Dashboard Guide](https://teamschools.zendesk.com/hc/en-us/articles/43413384789783-Academic-Health-Dashboard-Guide)               |
| **Academic Health Schools** | Where is failure concentrated by teacher, and which students near the 2.0 and 3.0 cusps need office hours? | [Academic Health Dashboard Guide](https://teamschools.zendesk.com/hc/en-us/articles/43413384789783-Academic-Health-Dashboard-Guide)               |
| **Cumulative GPA Monitor**  | Are high school cohorts on track for the unweighted cumulative GPA goal, and who sits just below 3.0?      | [Cumulative GPA Monitor Dashboard Guide](https://teamschools.zendesk.com/hc/en-us/articles/43413461831959-Cumulative-GPA-Monitor-Dashboard-Guide) |
| **Gradebook School Rollup** | What share of teachers have healthy gradebooks, by school and manager?                                     | [Gradebook Health Dashboard Guide](https://teamschools.zendesk.com/hc/en-us/articles/43377104764567-Gradebook-Health-Dashboard-Guide)             |
| **Gradebook Teacher View**  | What does my own gradebook need before the quarter closes?                                                 | [Gradebook Health Dashboard Guide](https://teamschools.zendesk.com/hc/en-us/articles/43377104764567-Gradebook-Health-Dashboard-Guide)             |

Direct links to each tab:

- [Academic Health Home](https://tableau.kipp.org/t/KIPPNJ/views/AcademicGradebookHealthSuite/AcademicHealthHome?:embed=y)
- [Academic Health Schools](https://tableau.kipp.org/t/KIPPNJ/views/AcademicGradebookHealthSuite/AcademicHealthSchools?:embed=y)
- [Cumulative GPA Monitor](https://tableau.kipp.org/t/KIPPNJ/views/AcademicGradebookHealthSuite/CumulativeGPAMonitor?:embed=y)
- [Gradebook School Rollup](https://tableau.kipp.org/t/KIPPNJ/views/AcademicGradebookHealthSuite/GradebookSchoolRollup?:embed=y)
- [Gradebook Teacher View](https://tableau.kipp.org/t/KIPPNJ/views/AcademicGradebookHealthSuite/GradebookTeacherView?:embed=y)

Related: the
[Importing Office Hours Rosters into DeansList](https://teamschools.zendesk.com/hc/en-us/articles/43411553089047-Importing-Office-Hours-Rosters-into-DeansList)
guide covers the export from the Academic Health Schools tab.

The **GPA Roster** links in every tab's header open a Google Sheet per region
with one row per student: quarter GPAs, Y1 GPA, cumulative GPA, advisory, ADA,
and IEP and 504 status.

## When everything refreshes

| What                               | When                                                                                           |
| ---------------------------------- | ---------------------------------------------------------------------------------------------- |
| All five tabs and the Landing Page | Once a day, overnight, at about 4:00 AM Eastern. Grades entered today appear tomorrow morning. |
| The GPA Roster Google Sheets       | Nightly, on the same schedule.                                                                 |
| Gradebook assignment expectations  | The next morning after T&L changes them in PowerSchool.                                        |

Every tab and tile prints its own "updated" stamp. The stamp is in Pacific time,
three hours behind our schools, so 1:26 AM PST is 4:26 AM Eastern.

> **Callout:** Entered today, visible tomorrow. If you fix a grade or an
> assignment in PowerSchool this afternoon, check the dashboard tomorrow, not
> tonight.

## If something looks wrong

Put in a data ticket. Open the help center's request form at
<https://teamschools.zendesk.com/hc/en-us/requests/new> and include:

1. Which tab you were on.
2. What the controls were set to: Academic Year, Marking Period, School, and
   anything else you changed.
3. What you saw and what you expected instead.
4. A screenshot, if you can. Crop out student names where you can.

The data team reads every ticket. A question about how to read a chart is fine
too; those tell us what the guides are missing.

---

## Screenshot manifest

| File                  | Guide media | Shows                                      |
| --------------------- | ----------- | ------------------------------------------ |
| `00-landing-page.png` | pending     | The Landing Page at network scope, 2026-27 |
