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
insert the region lines at their sorted position rather than after the opening
tag — Tableau writes the children of `<datasource-dependencies>` in plain ASCII
order of `name`, columns and column-instances interleaved, and rewrites that
order on every save, so inserting in order keeps a hand-edited sheet diffable
against a Desktop re-save. The claim covers only those inserted region lines:
the calc swaps that came later replace an element on the line it already
occupies, and were not re-sorted.

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

## 2026-09-10, build phase, Task 7

### `check_geometry --baseline` aborts on a dashboard the baseline never had

**Verified.** The brief's Step 5 and Step 6 both call
`check_geometry.py out.twb "Landing Page" --baseline base.twb`, expecting `rc=0`
on the clean file and `rc=1` on the reparent mutant. `Landing Page` is not in
`base.twb`, so `extract_gaps()` raises `StopIteration`, `main()` catches it and
calls `sys.exit("dashboard 'Landing Page' not found in baseline ...")` — exit 1
before one zone is read. Step 5 would have read as a geometry failure and Step
6's `rc=1` would have been the same abort, i.e. a mutation proof that passes
whether or not the mutation broke anything. Do this instead: check a dashboard
the baseline does not contain WITHOUT `--baseline`. The absolute-bounds mode
(every flow container's parent-minus-children gap in 0-3000) is the only mode
that applies to a new dashboard, and it is the mode the mutant has to fail in
for the proof to be worth running. Keep `--baseline` for the five pre-existing
dashboards, where it is the check that a new tab moved nothing.

### `<actions>` children are grouped by kind; the tail anchor breaks the group

**Verified by counting base.twb.** Inside `<actions>` the base holds 14
`<action>`, then 2 `<nav-action>`, then 6 `<edit-parameter-action>`, in that
order with no interleaving — the order Desktop writes and almost certainly the
content model, the same class of ordering that produced D2E8DA72 on `<pane>`
children earlier in this build. The brief's
`insert_before(t, "  </actions>\r\n", ...)` appends at the END of the element,
which would have put three `<action>` and nine `<nav-action>` after the
`<edit-parameter-action>` block. Do this instead: insert each new element at the
end of its OWN group — the URL actions before
`<nav-action caption='Open Teacher' ...>`, the nav-actions before
`<edit-parameter-action caption='Close panel' ...>` — and verify the grouping
after the build by listing the direct children in file order
(`17 action, 11 nav-action, 6 edit-parameter-action`). A tail anchor is safe
only in an element whose children are all one tag.

### An element absent from the workbook is an element the manifest has not declared

**Verified.** The brief's `button_zone` puts a `<tooltip-text>` inside each
`<button-visual-state>`. `<tooltip-text>` appears **0** times in `base.twb`, and
the workbook's `<document-format-change-manifest>` declares `BasicButtonObject`,
`BasicButtonObjectTextSupport`, `NavigationAction` and
`VizInTooltipHideWorksheet` and nothing else button-shaped — exactly the
situation `check_twb`'s feature check exists for
(`no declaration found for element 'x'`), and `check_unknown` would have
reported it against the reference as well. The four Tableau-written buttons in
this workbook carry `<caption>`, `<button-caption-font-style>` and
`<format attr='background-color'>` per visual state, nothing more. Do this
instead: before copying an element form quoted from ANOTHER workbook, count the
element in the target workbook and look for its feature in the target's
manifest; when either comes back empty, drop the element rather than the
manifest entry. The five header buttons ship caption-only, which is all the
label needs.

### The dashboard-level parameter block comes from a dashboard, not a worksheet

**Verified.** The brief specifies the
`<datasource-dependencies datasource='Parameters'>` block for `[Parameter 2]`
copied from `LP - Tile Y1 GPA` and re-indented. The worksheet-level copy carries
`<aliases>` but no `<members>`; the copy inside the `Academic Health Home`
DASHBOARD — which drives the same `p_Academic_Year` compact paramctrl this page
adds — carries both, and a `param-domain-type='list'` control populates its
dropdown from `<members>`. Copying the worksheet form would have shipped a year
control with an empty list, which nothing in the toolchain checks. Do this
instead: copy a dashboard-level element from a dashboard that already does the
same job, and assert the copy still contains the children that make it work
(`parameter2_dependencies()` raises if `<aliases>` or `<members>` is missing).

### `repository-location` is omitted from a never-published dashboard

**Inferred, not schema-verified.** All five existing dashboards open with
`<repository-location derived-from='https://tableau.kipp.org/...' />`, which
records where Server last published that sheet. `references/content-models.md`
lists a verified model for `worksheet`, `view`, `pane` and `zone` but none for
`dashboard`, so whether the element is optional there is not established from
the corpus. `Landing Page` has never been published, so there is no URL to
write, and every clone in Tasks 4 to 6 already drops the worksheet-level
`repository-location` for the same reason and passes `check_twb`. Do this
instead: omit it and let Server write it on the first publish; if Desktop
refuses the file with a dashboard content-model error at the Task 9 render, that
is the first thing to add back.

### A tall text zone's wrap behaviour is still unprobed, so every break is explicit

**Inferred, not render-verified.** This corpus has only short dashboard text
zones, and the one clipping observation on record is the Task 5 strip, which
clipped rather than wrapped. The definitions zone is 1350 px wide and 400 px
tall and holds ten entries whose sentences run to 380 characters. Rather than
bet on wrapping, every visual line is its own `<run>` with an explicit
`<run>Æ&#10;</run>` between them, and `definitions()` raises if any rendered
line — bold term prefix included — exceeds 110 characters; the longest built
is 109. The coverage grid takes the same bet twice over: it pads with spaces and
sets `fontname='Courier New'` on every run, so its alignment depends both on the
run text keeping its leading spaces and on `●` (U+25CF) and `—` (U+2014) being
fixed-pitch in that face. Do this instead: keep the explicit breaks and the
length assertion, and put "does the Courier grid line up, and does the
definitions zone clip at 20 lines" on the Task 9 render checklist as two named
questions rather than a general look-over.

### Zone geometry: `fixed-size` is pixels, `w`/`h` are units, and both are stated

**Verified.** A zone carries its size twice — `fixed-size` in pixels along its
parent's flow axis, `w`/`h` in the 100000-unit canvas space — and nothing checks
that they agree. At 1366 x 1500 one pixel is `100000/1366` units wide and
`100000/1500` units tall, so every size in this build goes through
`px_w()`/`px_h()` and the pixel figure that feeds `fixed-size` is the same
number that feeds the rounding. The children of a flow container must then sum
EXACTLY to the container along its flow axis; `check_geometry` tolerates a gap
up to 3000 units, which is 41 px of silent drift, so the last child in every row
and column takes the remainder (`ROOT_X + ROOT_W - x`) rather than a rounded
share. Measured on the finished file: all 11 flow containers have gap 0 and
every child starts exactly where the previous one ended. Do this instead: give
the last child the remainder, verify gap == 0 rather than "within tolerance",
and keep one non-fixed child per flow container — here the 114 px
`type-v2='empty'` spacer at the foot of the root column, which is the root's
only child without `is-fixed='true'`.

### Verbatim run output

Before the build step, against the Task 6 `out.twb`:

```text
assert rc=1
PASS task3
PASS task4
PASS task5
PASS task6
FAIL task7: AssertionError('dashboard')
```

After:

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
add_dashboard: +35359 bytes
add_actions: +4490 bytes
wrote /workspaces/teamster/.claude/scratch/tableau/lp/out.twb (2083671 chars)

assert rc=0
PASS task3
PASS task4
PASS task5
PASS task6
PASS task7

additive rc=0
stripped: {'worksheets': 19, 'dashboard': 1, 'dashboard-window': 1, 'sheet-windows': 19, 'nav-actions': 9, 'url-actions': 3, 'calcs': 3}
OK: remainder is byte-identical to base

check_twb rc=0
out.twb: CLEAN

geometry [Landing Page] rc=0
  Mode: without baseline (absolute bounds)
  OK: geometry consistent in 'Landing Page'

geometry [Academic Health Home] rc=0
  Mode: with baseline /workspaces/teamster/.claude/scratch/tableau/lp/base.twb
  OK: geometry consistent in 'Academic Health Home'

geometry [Academic Health Schools] rc=0
  Mode: with baseline /workspaces/teamster/.claude/scratch/tableau/lp/base.twb
  OK: geometry consistent in 'Academic Health Schools'

geometry [Cumulative GPA Monitor] rc=0
  Mode: with baseline /workspaces/teamster/.claude/scratch/tableau/lp/base.twb
  OK: geometry consistent in 'Cumulative GPA Monitor'

geometry [Gradebook School Rollup] rc=0
  Mode: with baseline /workspaces/teamster/.claude/scratch/tableau/lp/base.twb
  OK: geometry consistent in 'Gradebook School Rollup'

geometry [Gradebook Teacher View] rc=0
  Mode: with baseline /workspaces/teamster/.claude/scratch/tableau/lp/base.twb
  OK: geometry consistent in 'Gradebook Teacher View'
```

Rejected `--baseline` run on the new dashboard, kept because the exit code is a
tool precondition and not a geometry verdict:

```text
geometry [Landing Page, --baseline] rc=1
dashboard 'Landing Page' not found in baseline /workspaces/teamster/.claude/scratch/tableau/lp/base.twb
```

### Mutation proof

```text
  wrote ctrl2.twb: control  (byte-identical -- surgery is lossless)
CONTROL_OK

  wrote mut-2.twb: reparent 10 1
mutant geometry rc=1
  FAIL zone 14 (horz) gap is 24707, expected 0-3000
  Mode: without baseline (absolute bounds)
1 geometry failures in 'Landing Page'
```

Zone 10 is `LP - Tile Y1 GPA`; zone 1 is the header logo bitmap; zone 14 is the
`Tiles` row it was moved out of, which drops from four children to three and
loses exactly one tile's 24707 units. `check_geometry` catches it in
absolute-bounds mode, which is the mode a new dashboard is checked in — the
point of running the mutant without `--baseline`.

### Zone tree, as built

```text
46 vert   root, 98934u tall, 9 children, gap 0
  9  horz Header  80px   logo 167px | LP - Title (flex) | year 130px | 5 x 120px button
  14 horz Tiles   220px  4 tile sheets
  19 horz Regions 150px  4 strip sheets
  20 text         20px   Miami / Paterson HS footnote
  36 horz Directory 220px 5 vert panels, each card body 196px over guide 24px
  37 text         400px  definitions, 10 terms over 20 lines
  38 text         220px  coverage grid, Courier New 9pt, header + 7 rows + 2 notes
  44 horz Links   60px   label 100px | 3 roster sheets 60px | empty (flex)
  45 empty        114px  the root's one non-fixed child
```

46 zones, ids 1 to 46, no duplicate. 22 sheet zones, each named once: the 19
`LP - ` sheets and the three `Links - GPA Roster - <Region>` sheets. 22
viewpoints in the new window, one per sheet zone.

### Task 7 fix round: headings, the window-uuid barrier, the URL escape

**Ruling 14, and three reviewer minors.** The controller answered the open
headings question: each long-copy text zone opens with a bold 11 pt heading run
and a `<run>Æ&#10;</run>` break, out of the zone's existing height, not added to
it. `heading_run()` writes it with no `fontname`, so the coverage heading
inherits the zone's regular face while every grid line under it keeps
`fontname='Courier New'` — a run carrying its own face is what makes one
mixed-typeface text zone possible. Definitions now runs 21 lines in 400 px and
coverage 12 in 220 px; `task7` asserts both heading strings as a bold
`fontsize='11'` run, exactly once each.

**A lazy `.*?` under `re.S` needs a barrier at the element close.**
`read_window_uuids()` matched
`<window class='dashboard'[^>]*name='TAB'.*?<simple-id uuid='([^']*)' />` with
nothing stopping the lazy any at `</window>`. Every dashboard window in
`base.twb` carries its own trailing `simple-id`, so the match never crossed —
but a target window that lost one would have picked up the NEXT window's uuid
and pointed a header button at the wrong tab, with the build, the assertion and
every checker still green, because the uuid it found is a real uuid. Proved on a
two-window fixture whose first window has no `simple-id`: the old pattern
returns `{NEXT-WINDOW-UUID}`, the barriered `(?:(?!</window>).)*?` form returns
`None`. Do this instead: when a lazy any spans from one element's opening tag to
a child deep inside it, spell the close tag as a tempered barrier rather than
trusting the input to close first — and make the plan-comparison RAISE. The old
code printed a NOTE on a uuid that disagreed with the plan and carried on with
what it found, which is the wrong default for a value that silently reroutes
navigation; it now raises, the same way `read_roster_urls()` does.

**Interpolating an external value into an attribute means escaping it.** The
three roster URLs went into `expression='{url}'` raw. None of the three carries
an `&` today, so the file was well-formed and `ET.fromstring()` passed — but a
Google Sheets URL with a second query parameter would have produced `&` in an
attribute and broken the parse at the next build, and the same `esc()` every
other interpolated string in this script goes through was one call away. Do this
instead: route every interpolated value through `esc()` at the point it enters
markup, including values read out of the workbook itself, and do not treat "the
current data happens to be safe" as a reason to skip it.

**Corrected count.** The earlier entry said the base holds 7
`<edit-parameter-action>` and the finished file 17 / 11 / 7. Counted again over
the `<actions>` element in both files: the base holds 14 `<action>`, 2
`<nav-action>` and **6** `<edit-parameter-action>`, and `out.twb` reads 17 / 11
/ **6**. The grouping conclusion is unchanged; the number was wrong.

### Verbatim run output, fix round

```text
build rc=0
add_dashboard: +35613 bytes
add_actions: +4490 bytes
wrote /workspaces/teamster/.claude/scratch/tableau/lp/out.twb (2083925 chars)

assert rc=0
PASS task3
PASS task4
PASS task5
PASS task6
PASS task7

additive rc=0
stripped: {'worksheets': 19, 'dashboard': 1, 'dashboard-window': 1, 'sheet-windows': 19, 'nav-actions': 9, 'url-actions': 3, 'calcs': 3}
OK: remainder is byte-identical to base

check_twb rc=0
out.twb: CLEAN

geometry [Landing Page] rc=0
  Mode: without baseline (absolute bounds)
  OK: geometry consistent in 'Landing Page'
geometry [Academic Health Home] rc=0
geometry [Academic Health Schools] rc=0
geometry [Cumulative GPA Monitor] rc=0
geometry [Gradebook School Rollup] rc=0
geometry [Gradebook Teacher View] rc=0
```

The mutation proof was re-run unchanged after the fixes: `CONTROL_OK`, then
`mutant geometry rc=1` with `FAIL zone 14 (horz) gap is 24707, expected 0-3000`.
The two heading runs add 254 bytes to the dashboard and no zones, so the ids are
the same 1 to 46.

Barrier proof, on a fixture whose first window has no `simple-id`:

```text
old lazy-any regex  -> {NEXT-WINDOW-UUID}
barriered regex     -> None
```

## 2026-09-10, build phase, Task 8

### `publish()`'s return value does not carry `hidden_views` back

**Verified.** `server.workbooks.publish(item, ...)` returns a NEW `WorkbookItem`
built from the server's response, not the request object; the script reassigns
`item = server.workbooks.publish(...)`, and the fresh object's `hidden_views` is
`None` (it is a write-only field on the publish request, never populated from a
GET). The first run read `len(item.hidden_views)` after that reassignment, for
the `review-meta.txt` `hidden_count` field, and crashed with
`TypeError: object of type 'NoneType' has no len()` — after the publish, the
populate_views calls, and all seven renders had already succeeded, so the
publish itself was never wrong, only the bookkeeping written after it. Do this
instead: capture any value derived from the pre-publish `item` (here,
`len(item.hidden_views)`) into a local BEFORE the
`item = server.workbooks .publish(...)` line reassigns the name — the
request-side item and the response-side item are two different objects sharing
one variable name only by convention.

### `DEFAULT_VIEW` answers whether Server honors the `maximized` marker on a REST publish

**Verified.** Re-fetching the review copy by id after publish
(`server.workbooks.get_by_id(item.id)`, `populate_views`) and matching
`default_view_id` against the populated views resolved to `Landing Page` — the
window this build added with `maximized='true'` between `class` and `name` in
its `<window class='dashboard' maximized='true' name='Landing Page'>` element.
Four earlier workbooks correlated "the window with `maximized='true'` becomes
the default view on open" without a REST publish exercising it end to end; this
publish is the first to prove it rather than infer it.

### The `hidden_views` regex needs no change for `maximized`, only a read-through

**Verified.** The brief's regex,
`<window class='(?:worksheet|dashboard)'(?![^>]*hidden='true')[^>]*name='([^']*)'`,
already treats everything between `class='...'` and `name='...'` as an opaque
`[^>]*` span, so `maximized='true'` sitting in that gap on the `Landing Page`
window matches the same as any other attribute — no group boundary depends on
what comes between. The sheet names containing `&lt;` (e.g.
`Y1 Landing - BAN HS &lt;2.0`) came through the capture group still escaped, as
expected, and the existing `.replace("&lt;", "<").replace("&amp;", "&")` pass
unescaped them before the `publishable - live - added` set arithmetic — a set of
unescaped-both-ways names compared against `live_views` (itself unescaped, from
`base-meta.txt`) matched with no drift. `HIDING` came back as exactly the 10
pre-existing hidden sheets, and `LIVE will be` as exactly the five production
dashboards plus `Landing Page` — six names, matching the `expected_live` check
added before the publish gate.

### A session race fired once, mid-run, and the idempotent Overwrite absorbed it

**Verified.** The first `_with_retry` attempt published successfully
(`PUBLISHED: 55cac48f-15d0-4048-b219-bb8dfbf39700 into GPA-monitor-temp`), then
failed at the next server call with `FailedSignInError` /
`401002: Unauthorized Access` — another Tableau MCP process on the same PAT had
signed in and invalidated this session, exactly the failure mode
`test_zz_lp_pull.py`'s retry wrapper was built for. The wrapper re-entered a
fresh `with server.auth.sign_in(auth):` block, republished under the same
`ZZ-REVIEW 2026-09-10 AGHS landing page` name into the same project in
`Overwrite` mode, got the same review luid back, and completed the seven renders
and the re-fetch on that second attempt. No manual rerun was needed; the retry
the brief specified is what recovered it.

### Verbatim run output

```text
repack rc=0
  final.twbx: 28.4 MB
  packaged .twb byte-identical to source; CRLF 30102, bare LF 0
```

Donor check: `base.twb` unzipped from `base.twbx` and `cmp`'d against
`$lp/base.twb` on disk — identical, confirming the donor is the same production
download the base came from.

```text
HIDING ['GPA - BAN Avg cum GPA', 'GPA - Equity Gender', 'GPA - Equity IEP', 'GPA - Equity MLL', 'GPA - Equity Race', 'Goal vs Actual by Grade', 'Sheet 69', 'Tooltip - category reasons', 'Tooltip - failures by grade', 'Y1 Schools - Teacher Grade Distro']
HIDING 10 sheets; LIVE will be ['Academic Health Home', 'Academic Health Schools', 'Cumulative GPA Monitor', 'Gradebook School Rollup', 'Gradebook Teacher View', 'Landing Page']
PUBLISHED: 55cac48f-15d0-4048-b219-bb8dfbf39700 into GPA-monitor-temp
RETRY 1/3 after FailedSignInError: Failed Sign In Error:

	401002: Unauthorized Access
		Invalid authentication credentials were provided.
HIDING ['GPA - BAN Avg cum GPA', 'GPA - Equity Gender', 'GPA - Equity IEP', 'GPA - Equity MLL', 'GPA - Equity Race', 'Goal vs Actual by Grade', 'Sheet 69', 'Tooltip - category reasons', 'Tooltip - failures by grade', 'Y1 Schools - Teacher Grade Distro']
HIDING 10 sheets; LIVE will be ['Academic Health Home', 'Academic Health Schools', 'Cumulative GPA Monitor', 'Gradebook School Rollup', 'Gradebook Teacher View', 'Landing Page']
PUBLISHED: 55cac48f-15d0-4048-b219-bb8dfbf39700 into GPA-monitor-temp
RENDERED 'Academic Health Home': render-academic-health-home.png 454453 bytes
RENDERED 'Academic Health Schools': render-academic-health-schools.png 364037 bytes
RENDERED 'Cumulative GPA Monitor': render-cumulative-gpa-monitor.png 380966 bytes
RENDERED 'Gradebook School Rollup': render-gradebook-school-rollup.png 247583 bytes
RENDERED 'Gradebook Teacher View': render-gradebook-teacher-view.png 89813 bytes
RENDERED 'Landing Page': render-landing-page.png 721195 bytes
RENDERED 'Landing Page (Q1)': render-landing-q1.png 722897 bytes
DEFAULT_VIEW Landing Page
LIVE_VIEWS ['Academic Health Home', 'Academic Health Schools', 'Cumulative GPA Monitor', 'Gradebook School Rollup', 'Gradebook Teacher View', 'Landing Page']
review_luid=55cac48f-15d0-4048-b219-bb8dfbf39700
review_name=ZZ-REVIEW 2026-09-10 AGHS landing page
production_revision=25
default_view=Landing Page
live_views=Academic Health Home|Academic Health Schools|Cumulative GPA Monitor|Gradebook School Rollup|Gradebook Teacher View|Landing Page
hidden_count=10
1 passed in 85.63s (0:01:25)
```

The `review_url` line is omitted from this transcript (internal server
hostname); it is recorded in `$lp/review-meta.txt` and the Task 8 report.

Note: this run's first pytest invocation crashed on the `hidden_views`
bookkeeping bug above, AFTER the publish and all seven renders had already
succeeded server-side. The fix (capture `hidden_count` before the `publish()`
reassignment) required a second `pytest` invocation to get a clean pass and a
written `review-meta.txt`; the second invocation's `Overwrite` publish landed on
the same luid as the first, confirming the idempotency the retry design already
relied on.

## 2026-09-10, build phase, Task 9

### A dashboard's CSV is the first sheet's CSV on REST 3.25

**Verified.** The brief assumed `populate_csv` on a dashboard view returns one
CSV per sheet on that dashboard, citing REST 3.30. This server is 2025.1.9 at
REST API 3.25, and a dashboard view's `populate_csv` returns a single CSV: the
data of the dashboard's first sheet, with no delimiter or second header to mark
where another sheet would begin. So "fetch the four dashboards and compare their
sheets" is not a plan that survives contact with this version. The comparison
has to address each worksheet as its own view.

### `hidden_views` can only hide more views, never reveal one

**Verified.** The controller's ruling assumed the REST publish decides view
visibility purely from the `hidden_views` list, so that omitting a sheet from
that list would make it live even though `<windows>` marks it `hidden='true'`.
It does not. A window carrying `hidden='true'` is not in the publishable set at
all; `hidden_views` is applied to what the workbook already offers, and a name
that is not on offer is simply ignored. The first probe published with all
thirteen sheets omitted from `hidden_views` and came back with six views — the
six dashboards, exactly the same set as the review copy:

```text
LIVE will be [... 19 names ...]
PUBLISHED: 79aeaa71-25f8-4fd8-a97d-bb39f81e740b into GPA-monitor-temp
PROBE_LIVE_VIEWS ['Academic Health Home', 'Academic Health Schools',
 'Cumulative GPA Monitor', 'Gradebook School Rollup',
 'Gradebook Teacher View', 'Landing Page']
RuntimeError: probe has no live view named 'LP - Tile Y1 GPA'
```

The `LIVE will be` gate printed nineteen names and passed, because it was
checking the agent's intent rather than the server's answer. A gate on the
_request_ cannot catch a field the server ignores. The check that caught it was
looking up each sheet in `populate_views(item)` afterwards and raising on the
first miss.

### To query a hidden sheet, unhide it in the XML and publish a separate package

**Verified.** The workaround that does work: build a throwaway package whose
`<windows>` entries for the sheets under test have `hidden='true'` stripped,
publish that, query it, delete it. `repack_probe.py` does the strip by locating
each `<window class='worksheet' hidden='true' ... name='<name>'>` element by
name, removing only that element's `hidden` attribute, and asserting exactly one
match per name — `hidden='true'` occurs 158 times in this workbook and only 13
of them are the windows in question, so a blind global replace would have
unhidden seventy-odd sheets. Then rebuild the `.twbx` by copying every zip entry
across and substituting the edited `.twb` bytes, and verify the packaged bytes
match what you wrote before publishing.

The probe is a separate package from the review copy on purpose. The review copy
the user looks at keeps its own visibility; the probe carries the sheet-level
exposure and is deleted the moment the numbers are read.

### An equality where both sides are zero is a weak check, and should say so

**Verified.** `LP Students still needed (org)` and `Students still needed` both
return `0`, so the pair compares equal. They compare equal because the org is
currently above goal (measured 413, at 3.0+ 200 = 48.4% against a 45% goal
proportion), not because the org-only calc's arithmetic was exercised. A
shortfall calc that returned a constant zero would pass this check identically.
Recorded as a caveat in `render-notes.md` rather than reported as a clean pass:
re-check when the org sits below goal.

### `% at 3.0+` exports unformatted on both sides, which is inherited, not broken

**Verified.** Three of the four tile measures export percent-formatted (`69%`,
`8%`, `15%`); `% at 3.0+` exports as `0.484261501`. The source BAN exports the
same way, so the tile inherited the field format from its clone source and the
clone is faithful. It does mean the number the user sees on the tile comes from
the mark label's own format, which no CSV can confirm — only the crop.

### Images cannot reach the model in this harness, so the visual list is a hand-off

**Verified.** `check-output.sh` redacts every PNG and JPG at any size, so the
brief's "crop and `Read`" step is not available to the agent — halving the image
does not help, because the redaction is by content type, not by size. The crops
were produced anyway (seven files, 2732 px wide, from a 2732 x 3000 render that
is exactly 2x the 1366 x 1500 grid `crop_lp.py` assumes) and every visual check
is named in `render-notes.md` against the crop that shows it.

### The numbers, verbatim

| Measure                  | Tile sheet                   | Tile value  | Source sheet                          | Source value | Equal |
| ------------------------ | ---------------------------- | ----------- | ------------------------------------- | ------------ | ----- |
| % Y1 GPA at or above 3.0 | `LP - Tile Y1 GPA`           | 69%         | `Y1 Landing - BAN Network ≥3.0`       | 69%          | yes   |
| % Y1 Failing 2 or more   | `LP - Tile Course Failures`  | 8%          | `Y1 Landing - BAN Network Failing ≥2` | 8%           | yes   |
| % at 3.0+                | `LP - Tile Cumulative GPA`   | 0.484261501 | `GPA - BAN % 3.0+`                    | 0.484261501  | yes   |
| % healthy                | `LP - Tile Gradebook Health` | 15%         | `BAN Network`                         | 15%          | yes   |
| Students still needed    | `LP - Tile Cumulative GPA`   | 0           | `GPA - BAN Students needed`           | 0            | yes   |

All five equal as parsed numbers at default parameters (`p_Region` = `All`).

### The strip row sets

| Strip sheet                   | Regions                  | Values                                 |
| ----------------------------- | ------------------------ | -------------------------------------- |
| `LP - Strip Y1 GPA`           | Camden, Newark, Paterson | Camden 58%; Newark 74%; Paterson 52%   |
| `LP - Strip Course Failures`  | Camden, Newark, Paterson | Camden 16%; Newark 6%; Paterson 4%     |
| `LP - Strip Cumulative GPA`   | Camden, Newark           | Camden 0.484848485; Newark 0.484076433 |
| `LP - Strip Gradebook Health` | Camden, Newark, Paterson | Camden 3%; Newark 20%; Paterson 6%     |

The three MS/HS strips share the region set; the cumulative strip is a strict
subset. The four-sheet construction stands and the twelve-clone fallback is not
implemented. Whether the cumulative column pads a blank Paterson row or slides
its two rows up is a pixel question the user's reading of `crop-strip.png`
decides.

### The probe delete worked

`server.workbooks.delete(luid)` succeeded and a re-list of the project by
`tsc.Pager(server.workbooks)` no longer contained the luid: `PROBE_DELETED`.
Nothing was left behind in `GPA-monitor-temp` beyond the Task 8 review copy.

### Checks left to the user

`####` in any tile; clipped or ellipsised card text; a blank title or caption
line; a literal `[federated` or `[Parameters]` token; overlapping zones; strip
row alignment across the four columns; the Q1 render's tile titles reading `Q1`;
Courier grid alignment; the 130 px year control; the 120 px button captions. Two
need the live review copy rather than a still: hovering a guide slot showing no
tooltip, and the `tabdoc:goto-sheet` buttons and `nav-action` clicks landing on
the right tabs.

### Verbatim run output

```text
HIDING 10 sheets: ['GPA - BAN Avg cum GPA', 'GPA - Equity Gender', 'GPA - Equity IEP', 'GPA - Equity MLL', 'GPA - Equity Race', 'Goal vs Actual by Grade', 'Sheet 69', 'Tooltip - category reasons', 'Tooltip - failures by grade', 'Y1 Schools - Teacher Grade Distro']
LIVE will be ['Academic Health Home', 'Academic Health Schools', 'BAN Network', 'Cumulative GPA Monitor', 'GPA - BAN % 3.0+', 'GPA - BAN Students needed', 'Gradebook School Rollup', 'Gradebook Teacher View', 'LP - Strip Course Failures', 'LP - Strip Cumulative GPA', 'LP - Strip Gradebook Health', 'LP - Strip Y1 GPA', 'LP - Tile Course Failures', 'LP - Tile Cumulative GPA', 'LP - Tile Gradebook Health', 'LP - Tile Y1 GPA', 'Landing Page', 'Y1 Landing - BAN Network Failing ≥2', 'Y1 Landing - BAN Network ≥3.0']
PUBLISHED: 79aeaa71-25f8-4fd8-a97d-bb39f81e740b into GPA-monitor-temp
PROBE_LIVE_VIEWS [the same 19 names]
COMPARE % Y1 GPA at or above 3.0: tile='69%'(0.69) source='69%'(0.69) -> yes
COMPARE % Y1 Failing 2 or more: tile='8%'(0.08) source='8%'(0.08) -> yes
COMPARE % at 3.0+: tile='0.484261501'(0.484261501) source='0.484261501'(0.484261501) -> yes
COMPARE % healthy: tile='15%'(0.15) source='15%'(0.15) -> yes
COMPARE Students still needed: tile='0'(0.0) source='0'(0.0) -> yes
STRIP LP - Strip Y1 GPA: regions=['Camden', 'Newark', 'Paterson']
STRIP LP - Strip Course Failures: regions=['Camden', 'Newark', 'Paterson']
STRIP LP - Strip Cumulative GPA: regions=['Camden', 'Newark']
STRIP LP - Strip Gradebook Health: regions=['Camden', 'Newark', 'Paterson']
STRIP_SETS same_three=True base=['Camden', 'Newark', 'Paterson'] cum=['Camden', 'Newark'] subset=True
PROBE_DELETED
1 passed in 50.60s
```

Repack of the probe package:

```text
hidden='true' windows: 158 -> 145 (removed 13)
probe.twbx: 28.4 MB; twb entry Academic & Gradebook Health Suite.twb
packaged .twb byte-identical to the edited source
```

Crops:

```text
wrote header / tiles / strip / cards / definitions / coverage / links
render-landing-page.png (2732, 3000)
crop-header.png (2732, 192) 57939 bytes
crop-tiles.png (2732, 456) 85641 bytes
crop-strip.png (2732, 356) 88538 bytes
crop-cards.png (2732, 476) 176788 bytes
crop-definitions.png (2732, 816) 249039 bytes
crop-coverage.png (2732, 456) 54834 bytes
crop-links.png (2732, 344) 13064 bytes
```

## 2026-09-10, build phase, Task 10

### The launch catalog's `status` is a release switch, so a not-yet-live URL is `needs-review`

**Verified from the guide and `README.md`.** `docs/guides/launch-page-guide.md`
offers exactly two `status` values, and only `verified` entries render: "Setting
`verified` is what puts the tool in front of staff — it is a release switch, not
a quality note." Its "Taking a tool off the page" section names `needs-review`
as the value for an entry that should stay in the file but not appear. There is
no third "pending" state. So pointing the entry at a view that does not exist in
Production yet means `needs-review`, and the consequence is that the whole entry
— not just the new URL — drops off the page until the user publishes and someone
flips it back. Two things make that safe to do in this pull request rather than
deferring it: `groups.yml` carries `minimum_verified: 25` and the catalog holds
39 verified entries, so 38 is well clear of the gate; and the alternative,
leaving a `verified` entry pointing at a 404, is worse than a missing row.

**Controller ruling 17 overturned that trade.** A `needs-review` entry does not
degrade, it disappears: staff lose the working `Academic Health Home` link too,
for however long the Production publish takes. So the entry keeps its live URL
and `status: verified` in this pull request, and both edits — the URL and the
description clause — move to the hand-off note as a follow-up to make on publish
day. The status rule above still holds; only the timing changed. The general
form: a release switch that gates the whole record, rather than the field you
are changing, is not the place to stage a pending change.

### `pytest tests/launch` needs `--group docs`, or three tests fail on a missing import

**Verified.** The task brief's command was `uv run pytest tests/launch -q`. It
runs, and fails:

```text
E       ModuleNotFoundError: No module named 'mkdocs'
tests/launch/test_hook.py:27: ModuleNotFoundError
3 failed, 56 passed in 1.26s
```

`tests/launch/test_hook.py` imports `docs/hooks.py`, which imports `mkdocs`, and
`mkdocs` is in the `docs` dependency group rather than the default environment.
The published guide's own Step 3 already says
`uv run --group docs pytest tests/launch -v`; that command passes 59 of 59. Read
the failure as a missing dependency group, not as a broken catalog — the 56 that
pass are the catalog validation, and all three failures are the hook test.

### A fresh worktree has no `dbt_packages`, so `dbt parse` fails before it parses

**Verified.** First run in this worktree:

```text
Compilation Error
  dbt found 2 package(s) specified in packages.yml, but only 0 package(s)
  installed in dbt_packages. Run "dbt deps" to install package dependencies.
```

`dbt_packages/` is gitignored and is not carried into a new worktree, so
`uv run dbt deps --project-dir <worktree>/src/dbt/kipptaf` has to run once
before any `parse`, `compile` or `build` there. After `deps`, `dbt parse` exits
0 ("Unable to do partial parsing because saved manifest not found. Starting full
parse.") and the two added exposure refs resolve. Budget about 30 seconds for
the full parse.

### The output hook redacts this spec file whole, so edit it through a masking reader

**Verified.** `Read` and `grep` on
`docs/superpowers/specs/2026-09-10-academic-health-launch-page-design.md` return
a single `[redacted: secret material]` line: something in the file — a window
uuid or a long calculation name — trips `check-output.sh`'s high-entropy rule,
and the hook replaces every string in the result, not just the offending token.
The file is fine; the reader is the problem. Do this instead: print it through a
filter that masks any token of 18 or more alphanumeric characters, then apply
the edits with a script that asserts exactly one match per anchor. Both halves
are needed — the mask makes the prose readable, and the one-match assertion
replaces the eyeball check on the diff that the redaction makes impossible.

### The hand-off's donor claim is checkable in six lines, so check it

**Verified.** The claim "the extract came across untouched from Production" is
worth a derived value rather than a repack script's own success message.
Comparing `final.twbx` against `base.twbx` entry by entry:

```text
final.twbx bytes 28390025
entry counts 7 7 names equal: True
entries with differing CRC: ['Academic & Gradebook Health Suite.twb']
packaged twb == out.twb: True
```

Seven entries, one differing checksum, and that one is the `.twb` the build
edited. `zipfile.ZipInfo.CRC` is read from the archive's own directory, so this
costs nothing to compute and does not decompress the 28 MB extract.

## 2026-09-10, final review fixes

### The default-view guard has to run before the stripping, not after

**Verified.** `check_additive.py` counted `maximized='true'` after the
`dashboard-window` pattern had already removed the window that carries it, and
it accepted a count of `0` or `1`. That passes two broken files: one whose
marker was deleted outright, and one whose marker was moved to another
dashboard. After the strip both look exactly like a correct file, because the
correct file's marker is inside the window the strip removes. The guard now runs
before any stripping and requires three things — exactly one marker in the
edited file, exactly one in the base, and the edited one inside the
`<window class='dashboard' ... name='<the --dashboard argument>' ...>` opening
tag — and prints both counts and the window names it found when it fails. Proved
on the shipped file and on two mutants of it, built under
`.claude/scratch/tableau/lp/tmp-review/` and deleted afterwards:

```text
=== control out.twb -> exit 0
stripped: {'worksheets': 19, 'dashboard': 1, 'dashboard-window': 1, 'sheet-windows': 19, 'nav-actions': 9, 'url-actions': 3, 'calcs': 3}
OK: remainder is byte-identical to base
=== mutant A: marker removed -> exit 1
FAIL: default-view marker. Expected exactly one maximized window in each file, the edited one on 'Landing Page'. edited: 0 on []; base: 1 on ['Academic Health Home'].
=== mutant B: marker moved to Gradebook Teacher View -> exit 1
FAIL: default-view marker. Expected exactly one maximized window in each file, the edited one on 'Landing Page'. edited: 1 on ['Gradebook Teacher View']; base: 1 on ['Academic Health Home'].
```

The control's stripped dict is unchanged from the Task 8 run, so the guard costs
nothing the additive proof was already buying. Both mutants pass the old guard,
which is what made it worth replacing.

## 2026-09-10, root cause of the render redaction

### Why no image reached the model: the output scanner's entropy heuristic on raw base64

**Verified.** `check-output.sh` builds one string from every string leaf of the
tool result, strips only `data:...;base64,...` URIs, then redacts the whole
result if any run of `[A-Za-z0-9+/=_-]{120,}` is left that is not pure hex. An
image tool result carries its base64 payload as a bare `data` string (MCP:
`{type:"image", data, mimeType}`; Read:
`{type:"image", source:{type: "base64", media_type, data}}`), never as a `data:`
URI, and base64 is mixed case, so every render of any size trips it. The
heuristic dates from 2026-06-03 (`7b089acef`). It only started biting on
2026-09-03, when `a83666391` made the PostToolUse redaction actually apply
(before that the hook emitted `permissionDecision`, which PostToolUse ignores).
Today's `ad716e4d9` on `origin/main` (skip single-case runs) does not cover
base64. All four commits are Charlie Bini's.

The fix is not a rollback. It is an exclusion: drop the `data` payload of
`type: "image"` blocks before scanning, leave every other string in place. A
scratch copy of the hook with that change passed all 10 suites in
`tests/hooks/run_all.sh`; a 300-byte random image payload passed through in both
the MCP and Read shapes, and the same base64 inside a `type: "text"` block was
still redacted. The patched block and the probe harness are
`.claude/scratch/check-output.patched.sh` and
`.claude/scratch/hook-patch-proof.sh` on the build Codespace; the hook is a
protected file, so the owner applies it. Two regression cases belong in
`tests/hooks/test_fp_corpus.sh`: an MCP image block and a Read image block, each
with a 300-char base64 payload, asserted clean with `expect_allow_raw` against
the output hook path variable the helpers define.

## 2026-09-10, render-fix round (production revision 26 base)

### The page shipped to production before the defects were fixed, so the build had to rebase

**Verified.** The owner published the review copy to production at 20:02:27 UTC
as revision 26, and revision 26 therefore contains all 19 `LP - ` sheets, the
`Landing Page` dashboard, the 12 actions and the three `Calculation_77` calcs —
with every one of the four render defects. It is not reachable by staff:
`list-views` on the production workbook returns 5 views, and `Landing Page` is
not among them. Three consequences, none of which the hand-off anticipated:

- `build_lp.py` cannot be re-run. It is an ADDITIVE script: it clones sheets
  into a workbook that does not have them. Against a base that already has them
  it would duplicate every sheet name. The work becomes a PATCH script
  (`fix_lp.py`) over the shipped page.
- The old base cannot be reused either. Between revisions 25 and 26 the owner
  also changed four Gradebook Teacher View sheets (`Teacher sections panel`,
  `Teacher sections panel eyebrow`, `Tooltip - category reasons`,
  `Your sections grid`). Rebuilding from revision 25 would have silently
  reverted them.
- The extract moved with it. `% healthy` went 15% -> 14% and the gradebook
  strip's Newark cell 20% -> 19% between the two pulls. A recorded numbers table
  is a snapshot, not an oracle; re-run the tile-vs-source comparison rather than
  diffing against yesterday's numbers.

Do this instead: before resuming any workbook build, re-pull production and diff
the worksheet, dashboard, parameter, action and calc inventories against your
base. `test_zz_lp_repull.py` does it in one run and also hashes the clone
sources.

### `check_additive.py` has to strip BOTH sides once the addition has shipped

**Verified.** The checker stripped the `LP - ` elements from the edited file
only and compared the remainder to the base. That is right while the base
predates the addition and wrong the moment the addition is published into the
base: every LP element then reads as a deletion, and the checker fails on a
correct edit. Fixed by stripping the same patterns from both files and printing
both counts, which is backward compatible (a base without the elements yields
all-zero counts and identical behaviour) and asks the better question anyway: is
everything OUTSIDE these elements byte-identical? On this edit both sides strip
`{'worksheets': 19, 'dashboard': 1, 'dashboard-window': 1, 'sheet-windows': 19, 'nav-actions': 9, 'url-actions': 3, 'calcs': 3}`
and the remainder matches — which is also the proof that the owner's four
Teacher View sheets survived.

### `####` is a vertical-fit failure, and the diagnostic is the variant that works

**Verified by render.** All four tiles and three of four region strips printed
`####`; the cumulative strip printed `48.5%` correctly. The tempting reads —
number format, label width, a missing font, `mark-labels-cull` — are all wrong,
and each one is contradicted by a sheet in the same file:

| Hypothesis                 | Killed by                                                                          |
| -------------------------- | ---------------------------------------------------------------------------------- |
| number format              | no `text-format` on any of the four strips                                         |
| font missing on the server | the good strip uses the same `Tableau Semibold` / `Tableau Light`                  |
| `mark-labels-cull`         | the cumulative TILE has no cull rule and still printed `####`                      |
| cell style / text-align    | the cumulative tile and strip have identical style blocks, one fails and one works |

What actually separates them is how much vertical space one mark gets. The
cumulative strip is the only strip with two region rows instead of three (no
Paterson high school), so its rows are ~65 px against ~43 px, and it is the only
one whose 12 pt + 8 pt stack fits. The tiles all carry either an extra label
line or an oversized value run (30 pt, 42 pt) relative to the source BANs they
were cloned from, which render fine at 16 pt in five lines.

Do this instead: when one instance of a cloned pattern renders and another does
not, diff the SPACE each one gets before diffing its formatting. And take the
skill's catalog entry literally — removing a `<run>` line fixes `####`, growing
the box does not — so shorten the label rather than resize the zone, which also
leaves dashboard geometry untouched and `check_geometry` trivially clean.

### A mark label renders a field only if that field is on the Text shelf

**Verified by render, four cases in one image.** After the `####` fix the Y1 and
failures tiles read `of students` — the denominator ran as an empty gap, with no
error, no `####`, and no literal token. The two tiles that printed every number
(`LP - Tile Cumulative GPA`, `LP - Tile Gradebook Health`) have every field
their label references in `<encodings>` as `<text column=...>`. The two that did
not have the count on `<tooltip column=...>` only:

| Sheet                        | Label field                       | Shelf        | Rendered                  |
| ---------------------------- | --------------------------------- | ------------ | ------------------------- |
| `LP - Tile Cumulative GPA`   | `Calculation_7700000000000000003` | text         | `0 students still needed` |
| `LP - Tile Gradebook Health` | `Calculation_1052997927363395589` | text         | `52 of 363 teachers`      |
| `LP - Tile Y1 GPA`           | `Calculation_1000000000000000021` | tooltip only | `of students`             |
| `LP - Tile Course Failures`  | `Calculation_1000000000000000024` | tooltip only | `of students`             |

Adding a `<text>` encoding for the same instance fixed both
(`of 5,275 students`, `of 5,322 students`); the instance stays on Tooltip as
well, because the `<customized-tooltip>` references it too and a field may sit
on both shelves. This is the same failure shape as the skill's parameter-token
entry — blank, not loud — and it belongs beside it: **a `<customized-label>` run
resolves a `[datasource].[usr:...]` token only when that instance is also a
`<text>` encoding on the same pane.** A CSV check cannot see it, because the
value is in the data either way; only a render can.

### Desktop normalises a hand-built `.twb` on save, and the diff is legible

**Verified** by diffing our `out.twb` against the production revision 26 the
owner published from it. Desktop dropped orphan `<column>` declarations left by
filter removal (the "accepted residue" of Task 6), dropped zone attributes at
their default (`show-title='true'`, `show-caption='false'`), dropped a redundant
`fontsize='10'` from five nav-button captions, dropped empty `<zone-style>`
border blocks, re-solved every flow zone's `x`/`w`/`h`, and added a
`<repository-location>` to the dashboard pointing at the workbook it was
downloaded from — in this case the ZZ-REVIEW copy, which is how you can tell the
production publish came from the review copy rather than from `final.twbx`. None
of it changed behaviour. Useful corollary: a hand-built file that Desktop has
opened and saved is a free second opinion on which of your elements were
redundant.

### The output scanner still mangles image results, intermittently

**Verified.** Commit `574ee50d2` skips the base64 carrier of image blocks, and
one `get-view-image` at 500x550 did come back with pixels. Four later calls at
500x550, 520x570 and 480x530 came back as `media removed — rejected by API` with
`⛔ ... redacted by check-output.sh`, and the API's complaint names the media
type, not the data: the scanner is replacing the `media_type` string
(`image/png`) with `[redacted: secret material]`, which invalidates the block
even though the base64 survives. The reliable path this session was to let the
publish script write the render to disk (`view.image` bytes), crop it to the
region under test with Pillow, re-encode as a small JPEG, and `Read` that —
those went through every time. Worth adding to Charlie's fix: skip the whole
image block, `media_type` included, not just its `data` field.

## 2026-09-10, layout round: header, roster links, reference blocks

Three changes after the first render review: drop the five header nav buttons
(the tab cards below already navigate, so the header was a second copy of the
same affordance), move the GPA Roster links into the header where the other four
views in this workbook put them, and set the two reference text blocks side by
side.

### A dashboard text zone centres its content vertically

**Verified by measurement on a render.** The first attempt put both text zones
directly in one horizontal container 696 px tall. Both blocks rendered floating
in the middle of their zones and out of line with each other:

| Zone          | Content height | Zone height | Content started | Predicted by centring |
| ------------- | -------------- | ----------- | --------------- | --------------------- |
| definitions   | 338 px         | 696 px      | 179 px down     | (696-338)/2 = 179     |
| coverage grid | 157 px         | 696 px      | 269 px down     | (696-157)/2 = 269     |

Both match to within 5 px, so a `type-v2='text'` zone centres its content on the
cross axis. Nothing in the XML says so and nothing errors — it just looks like
someone left a gap. Do this instead: give a text zone a height close to its own
content and park the slack in a sibling empty zone, rather than letting one tall
zone hold both. Two blocks line up with each other only when their residual
centring offsets match, which means sizing each zone to its own content plus the
SAME margin, not to the same absolute height.

### `<zone-style>` matches a `<zone` prefix, so depth counting needs a lookahead

**Verified.** Brace-matching a `<zone>` element with
`re.compile(r"<zone\b[^>]*?(/?)>|</zone>")` never terminates: `\b` sits happily
between `zone` and `-style`, so every `<zone-style>` counts as another zone open
and the depth never returns to zero. `<zone(?=[ >])` fixes it. Worth having
because a nested zone tree cannot be edited safely with non-greedy `.*?</zone>`
— that stops at the first close, which is the wrong one for any container.

### `fixed-size` is content size; the cached `w`/`h` add the margins

**Verified against every zone in this dashboard.** On a 1366x1500 fixed canvas
the 98828-unit content column is 1349 px (73.25 u/px) and the full height is
1500 px (66.667 u/px). A zone whose `zone-style` carries `margin 4` measures
`fixed-size` as CONTENT and its cached size adds both margins — 586 units
horizontally, 533 vertically. A flow CONTAINER carries no margin, so its cached
size is exactly `fixed-size x scale`:

| Zone                      | fixed-size | cached  | check                   |
| ------------------------- | ---------- | ------- | ----------------------- |
| logo (margin 4)           | 167 px     | w=12811 | 167x73.25 + 586 = 12819 |
| year control (margin 4)   | 130 px     | w=10103 | 130x73.25 + 586 = 10109 |
| Miami footnote (margin 4) | 20 px      | h=1866  | 20x66.667 + 533 = 1866  |
| Header (container)        | 80 px      | h=5333  | 80x66.667 = 5333        |
| Tiles (container)         | 220 px     | h=14667 | 220x66.667 = 14667      |

Get this wrong and every sibling's `x` is off by 586 units, which is a sub-pixel
overlap that no checker and no render will show you.

### Copy a sibling dashboard's block verbatim; invention loses the details

**Verified.** The roster-links container was taken byte for byte from
`Academic Health Home` and only its ids and geometry rewritten. Two details a
hand-built copy would have got wrong: the `GPA Roster` label is
`fontcolor='#b9c7e6'`, a pale blue chosen for the navy header — the body copy of
the same label in the old footer position was `#001e62`, which on the navy
header would have been invisible — and the three link zones carry no
`fixed-size` at all, sizing instead through
`<layout-cache fixed-size-h='20' fixed-size-w='60' type-h='fixed' type-w='fixed' />`.
One thing NOT to copy: that container is 240 px against three 4978-unit links
needing 14934, so it ships with 2646 units of slack inside its own flow. Fine
where it already renders, but a container this build creates should close
exactly, so the copy was cut to 204 px.

### A duplicated edit block silently shadows the version you are editing

**Verified, self-inflicted.** A scripted edit inserted the whole layout section
twice. Python bound the LATER definition, so a rewrite applied to the first copy
changed nothing and the run produced byte-identical output — the same
`-2506 bytes` step delta as the previous run, which is exactly the signal that
looks like success. It was caught by dumping the zone tree from the OUTPUT and
seeing the old structure. Do this instead: when an edit to a build script
produces an unchanged byte delta, `grep -c` the function name before believing
the edit ran.

## 2026-09-10, shrink round: 60 px header, inline deltas, 1130 px canvas

### Shrinking a fixed canvas means recomputing every vertical measurement

**Verified.** Zone geometry is always 1/100000 of the canvas, so changing
`<size maxheight>` from 1500 to 1130 changes NO unit value on its own — it
changes what a unit is worth in pixels, and every `fixed-size` in the file
(which is in pixels) silently stops agreeing with the cached `h` beside it.
Server renders from the cached values, so the page renders at the old
proportions squashed into the new height; Desktop re-solves from `fixed-size`
and gets something different again. The two only agree if you rewrite them
together.

Done here by declaring the layout in pixels and generating the units: `ROWS`
gives each row of the outer vertical flow its height, `FILL` the children that
inherit their parent's height, `STACKS` the vertical sub-stacks, and
`relayout_vertical` turns the lot into units for whatever `CANVAS_H` says. Two
details that matter:

- **Round the rows independently and the column stops closing.** Seven rows each
  rounded to whole units summed to 98519 against an outer zone of 98518. The
  last row takes the remainder instead of its own rounding, with a guard that it
  stayed within a unit or two of its intended pixels.
- **Only rewrite `fixed-size` on the zones whose pixel height you changed.**
  Everything else keeps the pixel height it already had, so its `fixed-size` is
  already correct and touching it would introduce the very mismatch the exercise
  is avoiding. `VFIXED_ROWS` / `VFIXED_STACK` name the three.

### A text zone's content is taller than the arithmetic suggests

**Verified twice, by render.** The definitions block is 21 lines mixing 9 pt and
11 pt runs. Measured line spacing on a render is about 16.5 px, so 21 lines is
about 347 px and a 372 px zone (364 px of content box) looks like a comfortable
fit. It clipped: the last line vanished and Tableau printed its truncation
ellipsis after `school in the GPA goals source…`. Raising the zone to 420 px
fixed it.

Two things worth carrying: **the ellipsis is the tell** — a clipped text zone
does not just stop, it marks the cut, so grep the render for a trailing `…` you
did not write. And **the clip leaves visible empty space below it**, because
Tableau drops whole lines rather than part of one, so "there is still room under
the text" does not mean "nothing was cut".

### Stacked-then-dropped text hides its own wording bugs

**Verified.** The gradebook strip's detail run read `of <field> teachers`, but
that field already returns `52 of 363`. On the tile the same field is written
without the leading `of`. The strip's version was wrong from the start and never
visible: first the two-line label printed `####`, then the `####` fix dropped
the line entirely. Putting it inline finally rendered it —
`3% of 3 of 95 teachers`. Do this instead: when a fix makes previously invisible
text visible, read that text as new work, because it has never been reviewed
against a render.

### The deltas fit on the row all along; the constraint was only vertical

**Verified.** The `####` fix cut the strips to a bare value because a 12 pt
value stacked over an 8 pt detail line does not fit a ~43 px row band. Side by
side on the same line the pair fits easily: the column is 337 px wide and
`58%  (-9.4pp vs. 1 wk)` is about 130 px. All four strips now carry their detail
again. Worth remembering as the general move — when a label is too tall, try
making it wider before deleting content from it.

### The duplicate-block trap again, this time from a non-unique marker

**Verified, self-inflicted, second occurrence.** A scripted edit did
`t[:start] + new + t[end:]` where `end` came from
`t.index("# ---- default-view marker")`. That comment appears three times in the
file, so `end` resolved to the FIRST one, which sits BEFORE `start` — and the
slice duplicated everything between them instead of replacing it. Python bound
the later (stale) definitions and the run silently produced the old output. Do
this instead: never slice on a marker without asserting it is unique, and finish
any generated-file edit with a guard that every top-level `def` appears exactly
once. That guard is now in the cleanup step and would have caught both
occurrences.

### `trunk fmt` rewrites `Æ` escapes to the literal character

**Verified.** A pattern written as `r"Æ&#10;"` in a Python source file is
normalised by the formatter to the literal `Æ`, so a later scripted edit that
searches for the escape sequence finds nothing and silently does not apply. Cost
one round. Search for the literal character, or read the current file text
rather than assuming what you last wrote.
