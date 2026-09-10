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

## 2026-09-10, build phase, Task 1

### One live session per PAT: concurrent `tableau-mcp-server` processes invalidate a `tableauserverclient` sign-in mid-run

**Verified.** Three `tableau-mcp-server` node processes were alive on this
machine, all authenticating with the same Tableau personal access token
(confirmed by `ps -eo pid,etimes,cmd`, ages roughly 56, 30 and 12 minutes at
diagnosis time; still three processes, older, when re-checked from this
session). Tableau allows one live session per token, so every MCP (re)sign-in
invalidated whatever session the throwaway pytest test held. Symptoms across
three consecutive attempts of the _same, unchanged_ script: attempt 1 raised
`FailedSignInError`
(`401002: Unauthorized Access - Invalid authentication credentials were provided`)
at `server.auth.sign_in` itself; attempts 2 and 3 raised
`NotSignedInError: Missing site ID. You must sign in first.` from inside the
`with sign_in(...):` block, once from `populate_views`'s `baseurl` property.
None of this was a rotated or bad credential. Fix: wrap every server interaction
in a fresh `with server.auth.sign_in(auth):` block, retried up to 3x with a 5s
sleep, catching `NotSignedInError`, `FailedSignInError`, and
`ServerResponseError` with `code == "401002"`. Structural fix, not just retries:
never run two `tableauserverclient` scripts (a throwaway pytest and a live MCP
server) at once against the same PAT.

### A download whose session was invalidated mid-stream can still land intact on disk

**Verified.** Before the retry fix was added, one of the failed pytest attempts
still fully wrote `base.twbx` (29,799,451 bytes) and the unpacked `base.twb` to
`$lp` — the HTTP download had apparently already started streaming before the
session was invalidated, and completed anyway; the in-process exception came
later (in the `wb.views` access, see next entry), after the bytes were already
safely on disk. Do not assume a file is corrupt or partial just because the
script that wrote it raised — check its size against the expected floor and, for
anything meant to stand in for a live pull, verify it against the server's own
`updatedAt` before trusting or discarding it. Here that check was
`wb.updated_at` == `2026-09-10 13:40:42+00:00`, matching the owner's confirmed
republish time.

### `wb.views` is a lazy fetcher bound by `populate_views()`; it cannot be read after the sign-in block exits

**Verified.** `server.auth.sign_in(auth)`'s context manager signs out of the
server on `__exit__` (its own docstring: "Creates a context manager that will
sign out of the server upon exit"). `workbooks.populate_views(wb)` does not
eagerly fetch — it binds `wb._views` to a callable, and the `.views` property
(`workbook_item.py`) invokes that callable, making a live HTTP call, on _every_
access. The brief's original script read `v.name for v in wb.views` in the
`meta` list, built after the `with` block had already closed and signed out —
this fails deterministically with `NotSignedInError`, independent of the
concurrent-PAT issue above (it only didn't surface earlier because the
concurrency bug failed the test first, before reaching that line). Fix: capture
`view_names = [v.name for v in wb.views]` _inside_ the `with sign_in(...):`
block, alongside `populate_views`/`populate_revisions`, and use the plain list
afterward. `wb.updated_at`, `wb.show_tabs`, `wb.default_view_id`, and
`wb.revisions` are plain/already-consumed attributes and were fine to read
outside the block (the code already dereferenced `wb.revisions` inside the block
for `revision`, so this held by construction).

### The owner's 2026-09-10 13:40:42 UTC production republish

**Verified**, from a byte-for-byte diff of the fresh `base.twb` against this
morning's `aghs.twb` copy (08:17 UTC) using the brief's four regex `DIFF`
checks, and from `grep` against the fresh `base.twb`. Verbatim `DIFF` output:

```text
DIFF worksheets: removed=[] added=['Y1 Schools - Roster Close']
DIFF dashboards: removed=[] added=[]
DIFF parameters: removed=[] added=['[Parameter 15]']
DIFF actions: removed=[] added=['Band to roster']
```

Verbatim `base-meta.txt`:

```text
revision=25
updated_at=2026-09-10 13:40:42+00:00
show_tabs=True
default_view_id=e3f30b9d-e3aa-4342-9f00-21d0080eff53
live_views=Academic Health Home|Academic Health Schools|Cumulative GPA Monitor|Gradebook School Rollup|Gradebook Teacher View
```

Beyond the diff lines: the default-view marker
(`<window class='dashboard' maximized='true' name='Academic Health Home'>`,
confirmed by grep at `base.twb:24548`) moved onto Academic Health Home, matching
this log's earlier "default view is the `maximized='true'` window" lesson and
`wb.default_view_id` above resolving to that dashboard's view id.
`Calculation_76…` names are now taken — `grep -c "Calculation_76" base.twb`
returns 27 — so any new hidden calc this build adds must start numbering from
`Calculation_77…` to avoid a collision. The three
`Links - GPA Roster - <Region>` sheets (`Camden`, `Newark`, `Paterson`,
confirmed present by name) gained two action filters and `credit_type` /
`region` columns per the owner's publish notes relayed by the coordinator; not
independently re-derived from the XML in this task, only the sheet names and the
`Calculation_76` count were.

## 2026-09-10, build phase, Task 2

### The checker's own base-against-base run cost a `uv` venv build, not the regex

**Verified.** The first `check_additive.py base.twb base.twb ...` invocation ran
past the 120s foreground timeout and had to finish in the background; the output
showed `uv` spending 2m35s building a fresh `.venv` and installing 233 packages
(`Installed 233 packages in 2m 35s`) before Python ever started, not the 1.9 MB
regex sweep. Do the first `uv run` of a session as a throwaway or background
call so a real timeout isn't confused with a slow checker.

### Text-surgery stripping is exact: three real runs, one pass one fail

**Verified.** Base-against-base:

```text
rc=0
stripped: {'worksheets': 0, 'dashboard': 0, 'dashboard-window': 0, 'sheet-windows': 0, 'nav-actions': 0, 'url-actions': 0, 'calcs': 0}
OK: remainder is byte-identical to base
```

Control mutant (`mutate.py ... control`): `cmp` reported no difference, printed
`CONTROL_OK`. Mutant (`mutate.py ... set-attr 10 show-title true` on
`Gradebook School Rollup`) against the checker:

```text
rc=1
stripped: {'worksheets': 0, 'dashboard': 0, 'dashboard-window': 0, 'sheet-windows': 0, 'nav-actions': 0, 'url-actions': 0, 'calcs': 0}
```

with a diff whose first line was `@@ -23742,5 +23742,5 @@` followed by a line
naming `<zone ... id='10' name='BAN Network' show-title='false' ...>` on the
base side and `show-title='true'` on the edited side. The checker does not
confuse an unrelated zone attribute flip with a sanctioned addition — the
`stripped` dict stayed all-zero (nothing matched the LP-prefixed patterns) and
the byte comparison alone caught it.

### Nothing else surprised

No other trap surfaced in this task: the brief's zone-id-10 claim (`BAN Network`
inside `Gradebook School Rollup`) matched the diff exactly, and the argument
names in Step 1's `argparse` block needed no adjustment against the brief's
example invocation.

### The `calcs` pattern was order-dependent and untested, exactly as reviewed

**Verified.** Review caught it because a real `Calculation_77…` definition has a
`</column>` closer, but a _reference_ to that same calc inside a worksheet's
`datasource-dependencies` is a self-closing `<column .../>`, and the original
`calcs` regex's `[^>]*>` matched either shape. It was masked only by dict
iteration order (`worksheets` stripped first) and was never exercised, since the
real base has zero `Calculation_77` occurrences
(`grep -c "Calculation_77" base.twb` is 0). Fixed by requiring the char before
the opening tag's `>` not be `/` (`[^>]*[^/>]>`) and scoping the match to
datasource-level indentation (a `(?<=\n)` lookbehind plus a literal six-space
prefix, confirmed against `base.twb`: 94 datasource-level `<column>` definitions
at 6-space indent inside `rpt_tableau__gpa_goal_progress` alone, versus 16
self-closing 12-space references inside the `BAN Network` worksheet). `^` alone
would not have worked: `strip_elements` only passes `re.S` to `re.subn`, not
`re.M`, so an unescaped `^` matches only the start of the whole file, not each
line — a lookbehind on `\n` was required instead.

Proved with two temporary fixtures built from `base.twb` (deleted after use,
never committed): fixture-a added only a fake datasource-level
`Calculation_7700000000000000009` definition inside
`rpt_tableau__gpa_goal_progress`; fixture-b added, on top of that, a fake
self-closing reference to the same name inside `BAN Network`'s
`datasource-dependencies` (an existing worksheet — a real, non-additive
mutation). First attempt at building fixture-a corrupted the file: inserting at
`text.index("</datasource>", ...)` splices before the literal tag, not before
its line's leading indentation, so the existing 4-space indent bled into the
inserted block and the closing tag lost its own — fixed by inserting at
`text.rfind("\n", 0, tag_index) + 1` instead.

```text
fixture-a (datasource-level definition only) vs base:
rc=0
stripped: {'worksheets': 0, 'dashboard': 0, 'dashboard-window': 0, 'sheet-windows': 0, 'nav-actions': 0, 'url-actions': 0, 'calcs': 1}
OK: remainder is byte-identical to base

fixture-b (definition + self-closing reference in BAN Network) vs base:
rc=1
stripped: {'worksheets': 0, 'dashboard': 0, 'dashboard-window': 0, 'sheet-windows': 0, 'nav-actions': 0, 'url-actions': 0, 'calcs': 1}
FAIL: 8 diff lines; first 60:
--- base
+++ edited-minus-additions
@@ -10915,4 +10915,5 @@
           </datasources>
           <datasource-dependencies datasource='Parameters'>
+            <column caption='T' datatype='real' name='[Calculation_7700000000000000009]' role='measure' type='quantitative' />
             <column caption='Health basis' datatype='string' name='[Parameter 1 1]' param-domain-type='list' role='measure' type='nominal' value='&quot;Excluding comments&quot;'>
```

The `calcs` count stayed `1` in both (the legitimate definition was still
stripped correctly) and the diff named only the single inserted reference line —
the fix does not over- or under-strip. Re-ran the brief's Step 2 (base-vs-base)
and Step 3 (control + zone-10 mutant) afterward with no change in outcome:
`rc=0`/all-zero `stripped` for Step 2, `CONTROL_OK` then `rc=1` naming zone
`id='10'` for Step 3.

## 2026-09-10, build phase, Task 3

### A leading-whitespace anchor is not unique under plain substring match

**Verified.** The datasource-level `Gap to goal (pts)` column carries 6-space
indentation; three worksheet-level copies of the same column carry 12-space
indentation. `text.count()` on the anchor string
`      <column caption='Gap to goal (pts)' datatype='real' name='[Calculation_3466859908724272046]' role='measure' type='quantitative'>`
(6 leading spaces, as given) returned 4, not 1 — the trailing 6 of the 12
leading spaces on each worksheet-level copy, immediately followed by
`<column...`, is itself byte-identical to the 6-space anchor, so a plain
`str.count`/`str.replace` cannot tell the levels apart no matter how the
anchor's own indentation is chosen. Prefixing the anchor with the preceding
`\r\n` (forcing true line-start alignment) brought the count to exactly 1. Do
this instead: when an anchor's uniqueness rests on leading whitespace alone,
verify with `text.count(anchor)` in Python before trusting
`sub_once`/`insert_before` — not `grep -c` on an unanchored pattern, which can
also over- or under-count depending on flags — and if it is not 1, prepend
`\r\n` to the anchor and drop the duplicated newline from the inserted block by
using `sub_once` directly rather than the `insert_before` helper.

### `check-output.sh` can redact a lessons file's own reads

**Verified.** Once `lessons.md` accumulated a Task 2 entry with long
hex/UUID-shaped tokens, reading the file back — via `Read`, or via `Bash`
commands as content-free as `wc -l`, `file`, or a `tail -c 1` piped to a temp
file — came back as `[redacted: secret material]` every time, including for
outputs that only ever printed a line count or MIME type, never the triggering
bytes themselves. Do this instead: never `cat`/`Read`/`wc` this file directly
once it holds a long alnum token; write a small Python script that
regex-collapses long runs (`[A-Za-z0-9_.-]{10,}` -> `<TOKEN>`) to a separate
temp file first, then `Read` that sanitized copy — or append with a `Bash`
heredoc that never echoes the file's own content back.

### Verbatim run output

Step 1 (`grep -c "Calculation_77" base.twb`): `0` (prefix confirmed free).

Step 3 (assertion against a copy of base, before the build ran):

```text
rc=1
FAIL task3: AssertionError('Calculation_7700000000000000001')
```

Step 5 (build, assertion, check_additive, check_twb against `out.twb`):

```text
build rc=0
add_goal_calcs: +965 bytes
wrote /workspaces/teamster/.claude/scratch/tableau/lp/out.twb (1886081 chars)

assert rc=0
PASS task3

additive rc=0
stripped: {'worksheets': 0, 'dashboard': 0, 'dashboard-window': 0, 'sheet-windows': 0, 'nav-actions': 0, 'url-actions': 0, 'calcs': 2}
OK: remainder is byte-identical to base

check_twb rc=0
out.twb: CLEAN
```

## 2026-09-10, build phase, Task 4

### The brief's file-wide `simple-id` uniqueness assertion is false in the base

**Verified.** The task-4 assertion ended with
`ids = re.findall(...); assert len(ids) == len(set(ids))`. It failed on the
first build with `AssertionError('duplicate simple-id')` — and it fails on
`base.twb` too: of 150 `simple-id` values, 22 appear twice, every one of them a
`<worksheet name='X'>` and its own `<window class='worksheet' name='X'>` sharing
a uuid (`GPA - BAN % 3.0+`, `GPA - BAN Students needed`, and 20 more). That is a
shape Tableau itself writes, not corruption, and no clone can make it go away.
Do this instead: never assert a global invariant an untouched base does not
already satisfy. Scope the check to what the build added — collect the uuid
inside each `LP - ` worksheet and each `LP - ` window, assert there are exactly
ten, that they are pairwise distinct, and that each occurs exactly once in the
whole file. That is strictly stronger for the additions (it catches a clone that
kept its source's uuid, which is the real failure mode) and it is true.

### Deleting a filter does not delete the field from the worksheet

**Verified.** The brief's `apply_drop_filters` removed the `<filter>` element
and the `<slices>` line. Its own assertion then required
`"Calculation_4005670422414364681" not in y1` and `"[none:hos:nk]" not in y1`.
Both still matched: a filtered column-instance is carried in four places, not
two — the `<filter>`, the `<slices>` line, a `<column-instance .../>` line in
the worksheet's `datasource-dependencies`, and, when the instance wraps a
calculated field, that calc's own `<column>...</column>` definition inside the
same dependencies block. Do this instead: strip all four, in that order, and
after removing a calc's definition assert the bare calc name no longer occurs
anywhere in the clone — that assertion is what proves nothing else in the sheet
still referenced it, which is the only reason removing the definition is safe.

### A cloned element must not carry its own leading newline

**Verified.** Line-anchoring an element regex with a leading `\r\n` (the Task 3
lesson) makes the captured block start with that `\r\n`, and the block already
ends with one. Feeding that block to `insert_after(t, src, src + new)` then
emits `</worksheet>\r\n\r\n    <worksheet`, a blank line that
`check_additive.py` reports as a diff because its strip pattern
(`[ \t]*<worksheet ...>.*?</worksheet>\r?\n`) consumes only one newline. Do this
instead: keep the `\r\n` in the search pattern for uniqueness, then drop the
first two characters from the returned block (`blk[2:]`) so the clone starts at
its own indentation. Same rule for every removal regex: match `\r\n` + the line,
replace with the empty string, and consume no trailing newline, so the
surrounding lines close up exactly.

### Every anchor the brief quoted still matched the 2026-09-10 13:40 base

**Verified.** Checked all nine quoted strings with `text.count()` scoped to the
source worksheet block before running the build — the three title runs, the four
mark-label first runs, the `Region Filter` calc id
(`Calculation_4005670422414364681`, grades source) and the `Region filter` calc
id (`Calculation_5742832717263693013`, goals source). Each returned exactly 1.
Three of them return 2 or 3 when counted against the whole file
(`% At/Above 3.0` and `% Failing 2+` return 3, `Academic Health` returns 2,
because the MS/HS/Network BAN variants share label text), so the count must be
taken on the clone, never on the file. No anchor had to be changed.

### The cumulative tile's borrowed calc arrives without its own dependencies

**Inferred.** `GPA - BAN % 3.0+` does not carry `Students still needed`
(`Calculation_5262281088199017638`), so the brief's conditional branch applied:
copy its `<column>` and `<column-instance>` lines verbatim from
`GPA - BAN Students needed` and add one `<text column=...>` encoding — three
insertions, each asserted to match once. The copied calc's formula references
four fields (`Calculation_9485136151529756033`,
`Calculation_4693780698737655073`, `gpa_goal_proportion_org`,
`gpa_goal_proportion_region`) that the source sheet lists in its own
`datasource-dependencies` and the clone does not, and the source's `<style>`
text-format for that instance (`#,##0`) was not copied either, so a real-typed
count may render with decimals. Both were left alone because the brief specified
exactly three insertions. Do this instead: when borrowing a calculated field
between worksheets, copy the whole transitive dependency closure and its
`text-format` rule, or verify in Desktop that Tableau rebuilds the manifest on
open before treating a three-line copy as complete.

### Verbatim run output

Step 1 (assertion against the Task 3 `out.twb`, before the task-4 build):

```text
assert rc=1
PASS task3
FAIL task4: AssertionError('missing worksheet LP - Title')
```

First build (before the uuid assertion was rescoped):

```text
assert rc=1
PASS task3
FAIL task4: AssertionError('duplicate simple-id')
```

Step 5 (build, assertion, check_additive, check_twb against `out.twb`):

```text
build rc=0
add_goal_calcs: +965 bytes
add_title: +4519 bytes
add_tile_y1: +16444 bytes
add_tile_failures: +16753 bytes
add_tile_cumulative: +12052 bytes
add_tile_gradebook: +8652 bytes
wrote /workspaces/teamster/.claude/scratch/tableau/lp/out.twb (1944501 chars)

assert rc=0
PASS task3
PASS task4

additive rc=0
stripped: {'worksheets': 5, 'dashboard': 0, 'dashboard-window': 0, 'sheet-windows': 5, 'nav-actions': 0, 'url-actions': 0, 'calcs': 2}
OK: remainder is byte-identical to base

check_twb rc=0
out.twb: CLEAN
```

## 2026-09-10, build phase, Task 4 fix round

### A worksheet declares the whole input closure of every calc it carries

**Verified.** Copying a calculated field between worksheets is not a two-line
job. Audited every `<worksheet>` in `base.twb` with a script that collects the
`name='[...]'` of each `<column>` / `<column-instance>` in the sheet and then
resolves every `[Field]` reference inside every
`<calculation class='tableau' formula='...'>` in the same sheet: **633
worksheet-local calc definitions across 70 worksheets, zero references to an
undeclared field.** The first Task 4 build broke that invariant exactly once:
`LP - Tile Cumulative GPA` carried the borrowed
`Calculation_5262281088199017638` (`Students still needed`) whose formula reads
`Calculation_4693780698737655073`, `Calculation_9485136151529756033`,
`gpa_goal_proportion_org` and `gpa_goal_proportion_region`, none of them
declared in the clone. Do this instead: when lifting a calc into a sheet that
never carried it, lift its transitive input closure and its
`<style-rule element='cell'>` `text-format` line too, each as its own
`count()==1` edit at the position the donor sheet keeps it, and re-run the
closure audit on the clone. `build_lp.py` now does this in `assert_closure()`,
called on the tile right after it is cloned, so the invariant is enforced at
build time instead of being noticed in review. The rebuilt `out.twb` audits at
680 definitions across 75 worksheets, still zero undeclared references.

### `[^>]*>` matches straight through a self-closing tag

**Verified.** The filter-removal regex opened with
`<filter class='categorical' column='...'[^>]*>` and closed with `.*?</filter>`.
`base.twb` holds 6 self-closing categorical filters
(`<filter class='categorical' column='...' filter-group='3' />`). For one of
those the `[^>]*` runs through the `/`, the `>` of `/>` satisfies the
opening-tag match, and `.*?</filter>` then runs on to the **next** filter's
close — one substitution, two filters gone, no error. Demonstrated on a
two-filter synthetic:

```text
UNGUARDED [^>]*>: subs=1, filters left=0
GUARDED [^>]*(?<!/)>: subs=0, filters left=2
```

Do this instead: end the opening-tag match with `[^>]*(?<!/)>`. Note that the
`[^>]*[^/>]>` form used for calc columns is **not** interchangeable here: a
filter with no attribute after `column='...'` has `>` immediately after the
quote, and `[^/>]` would have nothing to consume. With the lookbehind the
self-closing filter simply does not match, so `cut_once` raises instead of
corrupting the sheet. `selftest_drop_filters()` runs at the top of `main()` and
proves all three halves on a synthetic block — the paired filter is removed, the
self-closing neighbour survives, and asking to drop the self-closing one raises:

```text
selftest_drop_filters: paired filter removed, self-closing filter intact, self-closing target refused
```

### A cloned tile inherits every workbook-global parameter its source reads

**Verified.** `LP - Tile Cumulative GPA` clones `GPA - BAN % 3.0+`, which
carries a `Grade filter` calc (`[grade_level] = [Parameters].[Parameter 10]`).
`[Parameter 10]` (`Grade view`, default `Grade 11`) has a visible control on the
Cumulative GPA Monitor tab, and Tableau parameters are workbook-global, so a
user changing the grade on that tab silently rescopes the landing-page tile. The
first draft's title said `high schools only`, which was simply untrue: the tile
shows one grade. Do this instead: before writing a tile title, list every
`[Parameters].[...]` the clone's filters and calcs read and make sure the title
names each one that narrows the number, or drop the filter. Here the filter
stays (the tile mirrors the Monitor BAN it clones, and the goals are per grade)
and the title carries both tokens —
`Grade <[Parameters].[Parameter 10]> · unweighted cumulative GPA · <[Parameters].[Parameter 11]>`
— with the caption naming where the control lives. The build asserts
`[Parameter 10]` is declared in the clone before it puts the token in the title;
a parameter token in a `<title>` whose parameter the sheet does not declare
renders as literal text.

### The live scratch scripts and the committed copies drift silently

**Verified.** Task 3 added six `trunk-ignore` lines to the committed
`assert_lp.py` and one to `build_lp.py` (`bandit/B314` above `ET.fromstring`)
but never copied the hook-formatted files back to `$lp/`. Task 4 then copied
`$lp/` **over** the committed copies, deleting every suppression, and
`trunk check --force --no-fix` went from clean to 21 security and 6 lint
findings — while the Task 4 report claimed the opposite, because the check had
been run before the commit hook reformatted the files and never after. Do this
instead: treat the copy-back step as part of the commit, not an afterthought —
`cp` the committed files to `$lp/`, `cmp` them, and re-run the build from the
copied-back scripts. Then run the repo's trunk command on the committed files
**after** the commit and paste the final summary line into the report, rather
than reporting a pre-commit run.

### Verbatim run output, fix round

```text
build rc=0
selftest_drop_filters: paired filter removed, self-closing filter intact, self-closing target refused
add_goal_calcs: +965 bytes
add_title: +4519 bytes
add_tile_y1: +16444 bytes
add_tile_failures: +16753 bytes
add_tile_cumulative: +13162 bytes
add_tile_gradebook: +8652 bytes
wrote /workspaces/teamster/.claude/scratch/tableau/lp/out.twb (1945611 chars)

assert rc=0
PASS task3
PASS task4

additive rc=0
stripped: {'worksheets': 5, 'dashboard': 0, 'dashboard-window': 0, 'sheet-windows': 5, 'nav-actions': 0, 'url-actions': 0, 'calcs': 2}
OK: remainder is byte-identical to base

check_twb rc=0
out.twb: CLEAN
```

## 2026-09-10, build phase, Task 5

### Dropping a region filter does not detach a tile from `p_Region`

**Verified.** `LP - Tile Cumulative GPA` borrowed `Students still needed`
(`Calculation_5262281088199017638`), whose formula branches on
`[Parameters].[Parameter 3]` (`p_Region`) in two places:

```text
AVG(IF [Parameters].[Parameter 3] = "All"
    THEN [gpa_goal_proportion_org]
    ELSE [gpa_goal_proportion_region]
    END)
```

Task 4 dropped the tile's own region _filter_, which is what makes the tile a
network number, and the tile has no parameter control of its own. But a Tableau
parameter is workbook-global and its current value is a property of the
workbook, not of the sheet that shows the control: a user who sets `p_Region` to
Newark on the Cumulative GPA Monitor tab silently reprices the landing page
tile's shortfall against Newark's goal, with nothing on the tile saying so.
Removing a filter removes a _filter_; it does not remove a dependency the
formula carries. Do this instead (Controller Ruling 10): enumerate every
`[Parameters].[...]` reference inside every calc a clone carries, not just the
ones in `<filter>`, and for each one either surface the parameter in the title
or resolve the branch at build time into a variant the clone owns. Here a third
datasource-level calc was added, `Calculation_7700000000000000003` /
`LP Students still needed (org)`, identical to the original with the whole
`AVG(IF ... END)` expression replaced by `AVG([gpa_goal_proportion_org])` in
both places, and the tile was repointed to it in all five places it referenced
the original: the worksheet-level `<column>` definition, the
`<column-instance>`, the `<text column=...>` encoding, the mark-label CDATA
token and the `#,##0` `<format attr='text-format'>` line. `assert_lp.py` now
asserts the tile contains `Calculation_7700000000000000003` and not
`Calculation_5262281088199017638`, and that the 003 formula contains neither
`Parameter 3` nor `gpa_goal_proportion_region`.

### A `//` comment in a formula reads as a field reference

**Verified.** `assert_closure()` collects `[Field]` tokens out of the raw
`formula='...'` attribute. The LP calcs open with
`// LP copy of [Students still needed] with the p_Region branch removed`, so the
first build after Ruling 10 — the first time an LP calc was written at worksheet
depth rather than only at the datasource — failed with
`[LP - Tile Cumulative GPA] calc references undeclared field [Students still needed]`
on a sheet that was in fact closed. Do this instead: split the formula on the
XML entity `&#10;` (formula newlines are entities, not real newlines) and drop
any line whose stripped form starts with `//` before scanning for references.
The closure invariant itself was never violated; only the checker was wrong, and
a checker that cries wolf on a correct sheet is the failure mode that gets
checkers disabled.

### Two of the four tiles already carry the region instance; all four carry the column

**Inferred from the file, then verified.** The brief's `strip_from_tile` re-adds
the `[region]` `<column>` and the `[none:region:nk]` `<column-instance>`
together, guarded by a single `if` on the instance. On this base that is wrong
in both directions. Measured on `out.twb` after Task 4: `LP - Tile Y1 GPA` and
`LP - Tile Course Failures` carry **both** (their dropped filter was on the
calculated `Region Filter`, `Calculation_4005670422414364681`, not on `region`
itself, and the sheets keep a region instance for other encodings);
`LP - Tile Cumulative GPA` and `LP - Tile Gradebook Health` carry the column but
**not** the instance. The single guard would therefore have written a second
`<column ... name='[region]' />` into the two sheets that need only the
instance. Do this instead: guard each line on its own `name='[...]'` probe, and
insert at the sorted position rather than after the opening tag — Tableau writes
the children of `<datasource-dependencies>` in plain ASCII order of `name`,
columns and column-instances interleaved, and rewrites that order on every save,
so inserting in order keeps a hand-edited sheet diffable against a Desktop
re-save.

### A `[usr:...:qk]` swap cannot be a `count()==1` literal edit

**Verified.** The brief's `extra` list for the cumulative strip is
`("[usr:Calculation_5262281088199017638:qk]", "[usr:Calculation_7700000000000000001:qk]")`,
passed to `clone_worksheet`, which asserts every edit anchor matches exactly
once. The instance token appears **four** times in that tile — the
`<column-instance>`'s own `name`, the `<format attr='text-format'>` field, the
`<text column=...>` encoding and the mark-label CDATA — plus the calc name
appears twice more (the `<column>` definition and the instance's `column`
attribute), six occurrences of the identifier in all. The edit raises rather
than silently repointing one of them. Do this instead: swap whole lines, not
identifiers. `cumulative_strip_edits()` reads the four lines out of the tile
with `paired_column()` / `one_line()` and pairs each with
`line.replace(LP_NEEDED_ORG, LP_NEEDED_REGION)`, so each swap is a literal the
clone carries exactly once and `clone_worksheet`'s own assertion still covers
it. The `<column>` definition is not swapped by string replacement at all: it is
regenerated from `LP_CALCS` at 12-space indentation, so the region variant's
caption and formula come from one source of truth rather than from an edited
copy of the org variant.

### The brief's label edits and its stated interface disagree

**Inferred.** The brief's Interfaces section requires "a two-line label: value,
then the one-week delta where the source has one", and Step 2's prose repeats
"the label cut to two lines". Its `add_strips` code only swaps the tile's header
run to a shorter string and leaves the other four or five runs in place — a
six-line label repeated on every region row. The prose was taken as the
requirement and the code's replacement strings were taken as the exact header
text, which now goes in the worksheet `<title>` instead: a per-row header
repeated three or four times down a narrow strip says nothing the column header
does not. Resulting labels: value then `(<Δ> vs. 1 wk)` on the two grades
strips; value then `<N> still needed (region goal)` on the cumulative strip (the
goals source has no weekly comparison, and the region shortfall is the number a
region lead acts on); value then `of <N> teachers` on the gradebook strip.
Flagged rather than silently resolved: if the reviewer wants the tile's full
label stack on the strips, the change is one argument per call.

### The strip title is static, which loses the cumulative tile's grade token

**Verified, unresolved.** Ruling 8 requires a tile title to name every parameter
that narrows its number. `LP - Strip Cumulative GPA` clones
`LP - Tile Cumulative GPA` and therefore keeps the `Grade filter` calc
(`[grade_level] = [Parameters].[Parameter 10]`), but the instruction for this
task is a short static header with no parameter token, so the strip's title is
`Cumulative GPA at or above 3.0` and does not say which grade. That is safe only
if the strip is laid out adjacent to the tile, whose title does carry
`Grade <[Parameters].[Parameter 10]>`. Whoever builds the dashboard zones must
either keep the two together or put the grade back in the strip header.

### Verbatim run output

Step 1 (assertion added first, run against the Task 4 `out.twb`):

```text
assert rc=1
FAIL task3: AssertionError('Calculation_7700000000000000003')
FAIL task4: AssertionError()
FAIL task5: AssertionError('LP - Strip Y1 GPA')
```

`task3` fails on the missing 003 column, `task4` on the raised
`len(added) == 18` simple-id count (9 LP worksheets, each with a window), and
`task5` on the first missing strip — all three expected before the build lands.

Step 3 (build, assertion, `check_additive`, `check_twb` against `out.twb`):

```text
build rc=0
selftest_drop_filters: paired filter removed, self-closing filter intact, self-closing target refused
add_goal_calcs: +1521 bytes
add_title: +4519 bytes
add_tile_y1: +16444 bytes
add_tile_failures: +16753 bytes
add_tile_cumulative: +12965 bytes
add_tile_gradebook: +8652 bytes
add_strips: +51660 bytes
wrote /workspaces/teamster/.claude/scratch/tableau/lp/out.twb (1997630 chars)

assert rc=0
PASS task3
PASS task4
PASS task5

additive rc=0
stripped: {'worksheets': 9, 'dashboard': 0, 'dashboard-window': 0, 'sheet-windows': 9, 'nav-actions': 0, 'url-actions': 0, 'calcs': 3}
OK: remainder is byte-identical to base

check_twb rc=0
out.twb: CLEAN
```

`add_tile_cumulative` is 197 bytes smaller than in Task 4: the borrowed
`Students still needed` definition is replaced by the generated 003 one, whose
`p_Region` branch is gone.

## 2026-09-10, build phase, Task 5 fix round

### Size a mark label against the row band, not against the tile it was cloned from

**Verified by arithmetic, not by render.** The strip sheets took their label run
sizes straight from the tiles they clone — 16pt for the value, 10pt for the
second line. A tile is one mark in a 170px zone; a strip divides the same zone
between a footnote and one row per region. About 130px of pane over three
regions is roughly 43px a row, and a 16pt line renders about 26px against a 10pt
line's about 16px, so 42px of text plus cell padding is already over budget with
Camden, Newark and Paterson, and further over the moment Miami's fourth row
lands. Three of the four strips also inherit
`<format attr='mark-labels-cull' value='true' />` from their tile, and on a Text
mark in a table a culled label does not clip — the cell renders **blank**, which
reads as missing data rather than as a layout problem. Do this instead: size a
cloned label against the row band of the sheet it is going into, not against the
sheet it came from, and treat `mark-labels-cull` as a silent failure mode rather
than a graceful one. All four strips now carry `fontsize='12'` on the value run
and `fontsize='8'` on the second line, fonts and colours unchanged, and `task5`
asserts exactly one of each and zero `fontsize='16'` or `fontsize='10'` inside
every strip's `<customized-label>` — so the tile sizes cannot creep back in
through a later copy-paste.

### A clone that keeps a parameter-driven filter needs the parameter in its title, strip or not

**Verified.** Task 5's instruction was a short static header on every strip, on
the grounds that a strip column has no room for a long title. That is right for
three of them and wrong for `LP - Strip Cumulative GPA`, which clones a tile
carrying `Grade filter` (`[grade_level] = [Parameters].[Parameter 10]`): a
grade-filtered number under a header that cannot say which grade is a number
nobody can check. Controller Ruling 11 overrides the static-title rule for that
one sheet; its header is now the single CDATA run
`Grade <[Parameters].[Parameter 10]> · cumulative GPA at or above 3.0`. Do this
instead: make the "does this title name every parameter that narrows the number"
test (Ruling 8) a property of the sheet's filters, not of the sheet's size — and
enforce it in code. `set_title()` now pulls every `[Parameters].[...]` token out
of the run it is about to write and raises unless the clone declares that
parameter, because an undeclared parameter token renders as literal text rather
than failing loudly. `task5` requires the token on the cumulative strip and
forbids `[Parameters].` on the other three.

### A worksheet background that was invisible on a tile appears behind row headers on a strip

**Verified.** `LP - Tile Gradebook Health` paints
`<style-rule element='table'><format attr='background-color' value='#001e62' />`
and reads perfectly well: it is a single mark with white label runs and no row
headers at all. The strip puts `region` on rows, which creates row headers
inside that same shaded table, so the region names would render in the default
dark header colour on navy. Nothing in the XML changed to cause it — adding rows
changed what the existing rule covers. Do this instead: when a clone gains a
shelf its source did not have, re-read the source's `<style>` rules for ones
whose scope silently widens. Ruling 12: the strip's sheet-level `<style>` gains

```text
<style-rule element='header'>
  <format attr='color' value='#ffffff' />
</style-rule>
```

copying the `attr='color'` form `Y1 Landing - Title` already uses on
`element='worksheet'`, inserted before the existing `element='table'` rule with
a one-match anchor (the sheet-level `<style>` is at 8-space indentation; the
pane-level one at 12, so the CRLF-prefixed anchor separates them). The tile's
own style block is untouched — verified by diffing both sheets in the output.

### A repointed calc has five reference sites, and one of them is not in the swap list

**Verified.** `cumulative_strip_edits()` swaps four lines to move the strip from
`Calculation_7700000000000000003` to `...001`: the `<column>` definition, the
`<column-instance>`, the `<format attr='text-format'>` line and the
`<text column=...>` encoding. The fifth site, the mark-label CDATA token, is
never in that list because `set_label()` rewrites the whole label from
`add_strips`' `label_runs` and writes `LP_NEEDED_REGION` directly. Both halves
are correct today and the assertion catches a mismatch (`...003` must not appear
in the strip, `...001` must), but the two live 60 lines apart with nothing
connecting them. Do this instead: when one edit path owns some of a symbol's
reference sites and another path owns the rest, say so in a comment at both
ends. `cumulative_strip_edits()`' docstring now names `set_label()` as the owner
of the fifth site.

### Verbatim run output, fix round

```text
build rc=0
selftest_drop_filters: paired filter removed, self-closing filter intact, self-closing target refused
add_goal_calcs: +1521 bytes
add_title: +4519 bytes
add_tile_y1: +16444 bytes
add_tile_failures: +16753 bytes
add_tile_cumulative: +12965 bytes
add_tile_gradebook: +8652 bytes
add_strips: +51825 bytes
wrote /workspaces/teamster/.claude/scratch/tableau/lp/out.twb (1997795 chars)

assert rc=0
PASS task3
PASS task4
PASS task5

additive rc=0
stripped: {'worksheets': 9, 'dashboard': 0, 'dashboard-window': 0, 'sheet-windows': 9, 'nav-actions': 0, 'url-actions': 0, 'calcs': 3}
OK: remainder is byte-identical to base

check_twb rc=0
out.twb: CLEAN
```

`add_strips` grows 165 bytes: the longer cumulative header and the four-line
`element='header'` style rule, less what the smaller font sizes save.

## 2026-09-10, build phase, Task 6

### A prefix-wide count in an earlier task's assertion is a tripwire for the next

**Verified.** `task4` ends with a file-wide sweep of `<worksheet name='LP - …'>`
and `<window … name='LP - …'>` blocks and asserts `len(added) == 18` — nine LP
worksheets, each with a window. The pattern is not scoped to Task 4's own five
sheets, so the ten sheets Task 6 adds turned that into 38 and `task4` failed on
work it does not own, in a task whose brief only mentions `task6`. Do this
instead: when an assertion counts everything matching a build-wide prefix, say
in its comment that the number is a running total for the whole build and expect
to raise it in every later task — or scope the regex to the sheets that task
owns. The count is now `38` with the comment naming all four sheet families
(title, 4 tiles, 4 strips, 5 cards, 5 guides).

### One `element='cell'` rule per pane: insert on one source, convert on the other

**Verified.** Controller ruling 13 asks for a left-aligned cell rule "inserted
before the existing `<style-rule element='mark'>`" on every card body and guide
sheet, but the two clone sources differ: `Y1 Landing - Title` has no
`element='cell'` rule at all (byte-counted: 0), while
`Links - GPA Roster - Newark` already carries one with
`<format attr='text-align' value='center' />` (byte-counted: 1). Inserting a
left rule before the mark rule on the roster clone would have put it _before_
the centred rule that already sits there, and the later rule for the same
element wins — a left rule that renders centred, with no error anywhere. Do this
instead: branch on whether the element already has a rule (insert when it does
not, convert the existing `value` when it does) and assert the END STATE —
exactly one `element='cell'` rule, `value='left'`, and zero `text-align`
`center` — rather than asserting the edit. `body_style()` in `build_lp.py` does
the branch; `task6` asserts the end state on all ten sheets.

### Take the semantics from a ruling, the bytes from the file

**Verified.** Ruling 13 quoted the new cell rule with its `<format>` line at 14
spaces and its `</style-rule>` at 12. The workbook writes pane-level style rules
at 14, their `<format>` children at 16 and the closing tag back at 14 —
confirmed against the roster sheet's own centred cell rule, which is the same
element at the same depth. Following the quoted bytes would have left one
element indented two spaces shallower than every sibling and reindented on the
owner's next Desktop save, which is exactly the noise that makes a later diff
unreadable. Do this instead: read a hand-written snippet in a ruling or brief
for what it says, not for how it is spaced, and copy indentation from the
nearest existing element of the same kind in the file.

### The 2026-09-10 13:40 republish's roster filters, counted before relying on them

**Verified.** Task 1 recorded from the owner's publish notes that the three
`Links - GPA Roster - <Region>` sheets gained action filters, without deriving
it from the XML. Counted directly this task on `Links - GPA Roster - Newark`:
three `<filter class='categorical' …>…</filter>` elements — the cross-source
`[none:school:nk]` filter targeting the grades source, plus
`[Action (Credit Type,Region,School)]` and `[Action (Region,School)]`, both
crossjoin group filters carrying the same `user:ui-action-filter='[Action3_…]'`
— and four `<slices>` columns, of which three go and `[Exclude ES]` stays. Do
this instead: pair a removal count (`n < 3` raises) with an assertion on the end
state — the `<slices>` element reduced to exactly one `<column>`, and that
column `[Exclude ES]` — because a count alone passes just as happily when a
fourth filter appears in a later republish and only three of four are cut.

### `mark-labels-cull` inherited from a clone source, the second time

**Verified.** Both Task 6 clone sources ship
`<format attr='mark-labels-cull' value='true' />` (byte-counted: 1 each), the
same attribute that blanked the Task 5 strips. A card label is about ten runs
across seven rendered lines and a guide label one; a culled label on a Text mark
does not clip, it renders the cell blank, so a culled card would have shipped as
an empty navy rectangle. Do this instead: treat `mark-labels-cull` as something
a clone always resets rather than something to check per sheet — `body_style()`
turns it off unconditionally, and `task6` asserts one `false` and zero `true` on
every one of the ten sheets, so no later clone of a card can reintroduce it
quietly.

### Orphaned dependency columns are the guide sheets' accepted residue

**Inferred, not render-verified.** Stripping every filter from the guide clones
leaves `[credit_type]` (with its four aliases), `[region]`, `[school]`,
`[school_level]` and the `[none:school:nk]` instance declared in
`<datasource-dependencies>` with nothing referencing them, the same residue Task
4's tile clones left and the same call the controller made then.
`assert_closure()` still passes because no `<calculation>` in the sheet names
them — the guide's only calc is the literal `&apos;Newark&apos;` — and
`check_twb` reports CLEAN, but neither of those proves Desktop is happy about an
unused declaration; only the Task 9 render will. Do this instead: keep the
residue (removing declarations is the change that has broken clones before), and
treat "the closure checker passes" as evidence the sheet is internally
consistent, not as evidence Desktop will open it.

### Verbatim run output

```text
build rc=0
selftest_drop_filters: paired filter removed, self-closing filter intact, self-closing target refused
add_goal_calcs: +1521 bytes
add_title: +4519 bytes
add_tile_y1: +16444 bytes
add_tile_failures: +16753 bytes
add_tile_cumulative: +12965 bytes
add_tile_gradebook: +8652 bytes
add_strips: +51825 bytes
add_cards: +26300 bytes
add_guides: +19492 bytes
wrote /workspaces/teamster/.claude/scratch/tableau/lp/out.twb (2043587 chars)

assert rc=0
PASS task3
PASS task4
PASS task5
PASS task6

additive rc=0
stripped: {'worksheets': 19, 'dashboard': 0, 'dashboard-window': 0, 'sheet-windows': 19, 'nav-actions': 0, 'url-actions': 0, 'calcs': 3}
OK: remainder is byte-identical to base

check_twb rc=0
out.twb: CLEAN
```

Before the build step, against the Task 5 `out.twb`:

```text
assert rc=1
PASS task3
PASS task4
PASS task5
FAIL task6: AssertionError('missing worksheet LP - Card Home')
```

`add_cards` is 26300 bytes for five 4.8 KB clones of a 4.2 KB source: the card
copy is longer than the two title runs it replaces, and dropping
`<layout-options>` gives back about 300 bytes. `add_guides` is 19492 for five
3.5 KB clones of a 6.7 KB source — the three filters, three slice columns, the
goals dependency block and the six-run tooltip together are about half the
source sheet.

## 2026-09-10, build phase, Task 6 fix round

### Deleting a customized tooltip turns the DEFAULT tooltip back on

**Verified.** `add_guides` removed `<customized-tooltip>` from the roster
clones, which is what the brief asked for and what the assertion checked
(`"<customized-tooltip>" not in g`). It does not silence the hover. A worksheet
with no `<customized-tooltip>` falls back to Tableau's default tooltip unless a
`<tooltip-style tooltip-mode='none' />` element says otherwise, and
`Links - GPA Roster - Newark` carries no `<tooltip-style>` at all — the roster
sheets want their tooltip. The guide mark's text encoding is the cloned
`'Newark'` calc, so all five placeholders would have popped `'Newark': Newark`
on hover, on a card whose visible text reads "Help guide: coming soon". The card
clones never had the problem: they inherit
`<tooltip-style tooltip-mode='none' />` from `Y1 Landing - Title`, the last
child of `<table>` straight after `<cols />`. Do this instead: when a clone
drops a customized tooltip, add the `tooltip-mode='none'` element in the same
edit, and assert the POSITIVE — `<tooltip-style tooltip-mode='none' />` present
exactly once — because an absence assertion passes on a sheet that still shows a
tooltip. `task6` now asserts it on all ten sheets, cards included, where it is
inherited rather than written.

### A match-count guard cannot catch a regex that runs on

**Verified by counting both forms over the whole base.** `add_guides` cut its
filters with `r"          <filter class='categorical' [^>]*>.*?</filter>\r\n"` —
the exact shape `apply_drop_filters()` was hardened against two tasks earlier,
minus the `(?<!/)>` negative lookbehind that `selftest_drop_filters()` exists to
prove necessary. Five of `base.twb`'s six self-closing categorical filters sit
at the same 10-space indent as the paired ones, and for each of them the
unguarded opening tag matches through its own `/>` and the following
`.*?</filter>` runs on to the NEXT filter's close, deleting two elements in one
substitution. The numbers, base-wide: the unguarded pattern matches **349**
times and the guarded one matches **349** times as well — the run-on removes one
match while adding it to another — but 5 of the spans differ and the unguarded
form deletes 139188 bytes against the guarded form's 138616, 572 bytes of
collateral. So the `if n < 3: raise` guard in `add_guides` could never have
caught it: a run-on lowers the match count rather than raising it, and a lowered
count still cleared the threshold. Nothing was actually corrupted — all three
roster filters are paired, so the two forms agree on that sheet — but the safety
came from the input, not from the code. Do this instead: when reusing a pattern
the codebase has already hardened, copy the guard along with the shape, and read
a count assertion as evidence about how many matches there were, never about
where they ended. All four removals in `add_guides` are now `\r\n`-anchored at
the line start (a 10-space-indented literal is a substring of a
12-space-indented one) and the filter cut carries `(?<!/)>`; the trailing `\r\n`
came off each pattern in exchange, so the byte count stays balanced and
`add_guides` grew by exactly the five new `<tooltip-style>` lines, 5 × 47 = 235
bytes.

### Verbatim run output, fix round

```text
build rc=0
selftest_drop_filters: paired filter removed, self-closing filter intact, self-closing target refused
add_goal_calcs: +1521 bytes
add_title: +4519 bytes
add_tile_y1: +16444 bytes
add_tile_failures: +16753 bytes
add_tile_cumulative: +12965 bytes
add_tile_gradebook: +8652 bytes
add_strips: +51825 bytes
add_cards: +26300 bytes
add_guides: +19727 bytes
wrote /workspaces/teamster/.claude/scratch/tableau/lp/out.twb (2043822 chars)

assert rc=0
PASS task3
PASS task4
PASS task5
PASS task6

additive rc=0
stripped: {'worksheets': 19, 'dashboard': 0, 'dashboard-window': 0, 'sheet-windows': 19, 'nav-actions': 0, 'url-actions': 0, 'calcs': 3}
OK: remainder is byte-identical to base

check_twb rc=0
out.twb: CLEAN
```
