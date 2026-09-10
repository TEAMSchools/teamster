# Landing page build: lessons and traps log

Running log for #5235, kept so the `tableau-workbook-xml` skill can absorb what
held up and what did not. One entry per lesson. Marks: **Verified** means
observed against this server or this harness on the date given; **Inferred**
means consistent with a working file but not probed. Newest entries at the
bottom. Every script written during the work is in `scripts/` beside this file,
including throwaway pytest files that were deleted from `tests/` after use.

## 2026-09-10, review and design phase

### Harness: no image reaches the model, at any size

**Verified.** `mcp__tableau__get-view-image` output is redacted by
`check-output.sh` every time (base64 reads as a high-entropy string). `Read` on
a PNG or JPG on disk is redacted too, including an 18 KB 683 by 450 JPEG crop.
The skill's "crop the region and read the crop" advice did not hold in this
harness on this date; no crop size got through. What worked: the user pasting
screenshots into the conversation, and reading the workbook XML instead of the
render. For numbers, the data API (`populate_csv`, `get-view-data`) is the
render-free path. The skill should say: plan for zero image reads, ask the user
for screenshots, verify numbers through data.

### `get-view-data` on a dashboard returns the first sheet only, or nothing

**Verified.** On OKRTS and DDI landing pages it returned `"\r\n"`; on CARAT it
returned one sheet's CSV (the average-scores table). A landing page made of text
zones and link sheets has no data to return. Do not read an empty result as an
MCP failure.

### Reading a dashboard from XML replaces the render for structure

**Verified.** `dump_landing.py` walks a dashboard's `<zones>` and prints the
tree with zone type, sheet name, parameter, and the concatenated `<run>` text of
every text zone. `dump_sheets.py` prints per-worksheet title, caption,
mark-label runs, tooltip runs, string-literal calcs, shelves and encodings.
Between them they recovered every word on all three reference landing pages and
the whole suite, which is what the review was written from. They belong in
`docs/tableau-xml/scripts/` if the skill adopts them.

### Download without the extract is a complete `.twb`

**Verified.** `include_extract=False` returns a 189 KB `.twbx` whose packaged
`.twb` is the full workbook XML. The skill's warning that this gives "a stub" is
about republishing (the data is gone), not about reading. For read-only work it
is the right call: 30 MB per pull otherwise.

### A republish claim is checked with `updated_at` and `cmp`, not taken on faith

**Verified.** The owner said they had published a new production version. A
fresh pull had the same `updated_at` (08:17 UTC) and was byte-identical to the
morning's copy; `list-workbooks` with `updatedAt:gte:` listed 20 workbooks
modified since and the suite was not among them. The publish had landed on a
scratch copy. Pull, compare, then decide whether to rebase.

### Navigation XML exists on this server and does not need to be invented

**Verified by grep, not by publish.** Two Tableau-written forms:

- A sheet-click "Go to Sheet" is a `<nav-action>` in `<actions>`:

  ```xml
  <nav-action caption='Open Teacher' name='[Action18_A5B48E9807DE44888A395CF989A57E39]'>
    <activation type='on-select' />
    <source dashboard='Gradebook School Rollup' type='sheet' worksheet='Teacher sections panel' />
    <params>
      <param name='sheet' value='Gradebook Teacher View' />
    </params>
  </nav-action>
  ```

  Present in the suite itself. Command-style `<action>` elements in this corpus
  carry only `tsc:tsl-filter`; there is no `tsl-navigate` command.

- A navigation button is a `dashboard-object` zone whose `<button>` has
  `action='tabdoc:goto-sheet window-id=&quot;{uuid}&quot;'` and one
  `<button-visual-state>` with `<caption>` and optional `<tooltip-text>`.
  Present in `Gradebook and GPA Dashboard`. The `window-id` is the target
  dashboard's **window** `simple-id` (from `<windows>`), not the `<dashboard>`
  element's `simple-id`; the two differ. Toggle buttons reference the same
  window uuid.

Neither form has been publish-and-click verified by this project. A render
cannot click. The user does.

### The default view is the `maximized='true'` window, not the first tab

**Verified by correlation on four workbooks.** REST `defaultViewId` matched the
`<window class='dashboard' ... maximized='true'>` entry in every case: suite
(Teacher View), CARAT (Roster), DDI (Module Dashboard), OKRTS (Landing Page).
Tab order is `<windows>` order; the default view is whichever window is
maximized, and they need not agree. The suite opens on the Teacher View for
exactly this reason. To make a new dashboard the default, move
`maximized='true'` to its window. That is a one-attribute edit on an existing
window element, and any "additive only" checker has to normalize it out. Whether
Server honors the attribute on a REST publish is checked by reading
`wb.default_view_id` off the published item.

### `<repository-location>` at worksheet depth blocks a title

**Verified from the content model and the base.** The suite's BAN sheets carry a
`<repository-location>` as their first child; the model is
`((layout-options? | repository-location?), table, simple-id)`, so a clone that
needs a `<title>` or `<caption>` must drop the repository-location first.

### Choose clone sources by what they do not carry

**Verified by reading.** `Sheet Card - expectations` looked like the natural
card template and carries two action filters bound to the Teacher View plus
gradebook-specific calcs. `Y1 Landing - Title` is a static text mark with one
slice and no filters, and is the cheaper skeleton for any static card. The
roster link sheets carry a cross-datasource filter and a second datasource that
a placeholder link does not need.

### The auto-mode classifier blocks a download-everything pytest

**Verified.** A throwaway test that paged every workbook on the site and
downloaded each `.twb` was denied. The same test scoped to four named luids ran.
Narrow the ask instead of retrying.

### Harness mechanics that cost a call each

- `uv` is not on `$PATH` in Bash here; `~/.local/bin/uv`.
- Bash `cd` does not persist across calls ("Shell cwd was reset"); every path
  absolute.
- Bash may not name `.claude/hooks/*.sh` even to `grep` them (Rule 2); use
  `Read`.
- Markdown tables fail MD060 until the commit hook re-pads them; commit and let
  the hook do it rather than hand-aligning.

### Design lessons from the three reference landing pages

Recorded here because they shaped the spec and would apply to any landing page
built through the skill:

- All three share one skeleton: navy header with logo, a "How can this dashboard
  help me?" tab directory, one question-titled data block, and a status
  vocabulary with a legend. OKRTS's directory entries end in a colored "Visible
  to:" line and read best.
- All three accreted: hidden show/hide panels of analysis, ten filters on a
  landing block, a prose directory that says "3 tabs" on a five-tab workbook.
- Visible defects only the screenshot showed: colliding goal labels on CARAT, an
  empty Bright Spots panel and clipped headers on DDI, a heatmap column that
  renders red for zeros on OKRTS.

### `logs/` is gitignored repo-wide

**Verified.** `.gitignore` line 19 is `logs/`, so a lessons log placed under
`docs/tableau-xml/logs/` is silently never added; `git add <dir>` prints the
ignore hint and the commit chain stops. This log lives under
`docs/tableau-xml/lessons/` for that reason. Check `git check-ignore -v <path>`
before choosing a directory name for durable notes.
