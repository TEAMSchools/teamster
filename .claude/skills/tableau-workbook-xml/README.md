# tableau-workbook-xml

A Claude Code skill for editing Tableau workbooks as XML. This page is for
people. The skill itself, [SKILL.md](SKILL.md), is written for the agent.

## What it does

A Tableau workbook (`.twb`, or `.twbx` with the data packaged in) is an XML
file. Some changes are faster to make in that XML than in Tableau Desktop: the
same tooltip on 12 sheets, a caption on every card, a zone moved in a dashboard,
a number format on one column. Some problems only show up there: a workbook that
publishes to Tableau Server fine but Desktop refuses to open.

This skill gives Claude the procedure for that work and the things that went
wrong the first time we did it. It was built from one project in September 2026:
editing the `Academic & Gradebook Health Suite` workbook by hand, publishing to
a scratch project, and rendering the result. Everything in it was learned there.

## When it loads

Claude loads the skill on its own when a request matches its description: hand
editing a `.twb` or `.twbx`, adding tooltips, titles, captions or mark labels,
restructuring dashboard zones, changing number formats, copying an element
between workbooks, publishing or rolling back a hand-edited workbook, or
diagnosing a Desktop error such as `no declaration found for element` or
`missing elements in content model`.

You can also load it directly by typing `/tableau-workbook-xml` at the start of
a request. Do that when the phrasing might not match, for example a plain
"republish this workbook".

## What Claude will do with it

1. Download a fresh copy of the workbook and record when it last changed.
2. Write a check that fails on the current file, make the edit, and confirm the
   check passes. Then break the edited file on purpose and confirm the check
   catches that too.
3. Run two checkers that catch what Tableau Desktop rejects and Tableau Server
   does not.
4. Repack the `.twbx` and publish it to a non-production project. Claude asks
   which project before the first publish and falls back to `GPA-monitor-temp`.
5. Render the dashboard and look at the image, because valid XML has rendered
   `####`, blank lines, clipped captions and missing legend entries.
6. Hand back the `.twbx` and a review copy, with a list of what was verified,
   what was inferred, and what still needs a person to hover, click, or open the
   file in Desktop.

## What Claude will not do with it

Publish to the production project. The skill allows that only after you type an
explicit instruction naming production as the target and then answer yes to a
second "Are you sure?" question. A production URL, a request to fix something in
production, a deadline, or a prior conversation do not count. Rolling back a bad
production publish is treated the same way. After any production publish, Claude
asks you to open the production workbook yourself, because nothing in the skill
can guarantee the file is not corrupted.

## How much of it is true

Every claim in the skill is marked. **Verified** means it was seen in a render
or in a Desktop error. **Inferred** means it was consistent with a working file
but never rendered. Two inferences in the source project were wrong, which is
why the marks exist.

One question is still open. Tableau writes tooltip text in two different XML
forms, a hand-built copy of one form printed its placeholders literally instead
of resolving them, and nobody has yet confirmed by hovering which form works.
The skill says so and tells Claude to copy a working tooltip from the same
workbook rather than compose one.

A separate file, `references/unverified-warnings.md`, lists risks an experienced
Tableau developer raised in review that this project never tested, each with the
experiment that would settle it. Claude treats those as hypotheses.

## What is in the folder

| File                                | Holds                                                                                   |
| ----------------------------------- | --------------------------------------------------------------------------------------- |
| `SKILL.md`                          | The procedure, a symptom-to-fix list, and the five scripts with their commands          |
| `references/content-models.md`      | Element ordering rules Desktop enforces, and the feature manifest                       |
| `references/dynamic-text.md`        | Which text surfaces resolve field and parameter placeholders; the open tooltip question |
| `references/layout-and-zones.md`    | Dashboard geometry, `fixed-size`, why text clips, the card layout idiom                 |
| `references/formatting.md`          | Number formats, the paragraph-break marker, line-ending traps, regex traps              |
| `references/build-workflow.md`      | Code for download, publish gate, render, and cross-workbook merges                      |
| `references/failure-catalog.md`     | Every failure observed, as symptom, cause, fix, with exact error strings                |
| `references/unverified-warnings.md` | Review hypotheses with probes; nothing here is verified                                 |

The scripts live in `docs/tableau-xml/scripts/` and are referenced from the
skill by path: two checkers, a mutation tool for testing your own checks, a
repacker, and a download-publish-render template.

## Contributing

Corrections go in the skill references, not in `docs/tableau-xml/`; the numbered
files there are pointer stubs. Keep the Verified and Inferred marks honest: a
claim moves from Inferred to Verified only after a render or a Desktop open, and
a claim from your own Tableau experience goes in `unverified-warnings.md` with a
probe until then. Run
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files>` before
pushing markdown.
