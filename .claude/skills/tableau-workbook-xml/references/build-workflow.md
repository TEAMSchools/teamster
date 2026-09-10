# Build workflow: code detail

The step order lives in `SKILL.md`. This file holds the code behind each step
and the traps each snippet guards. All claims are **Verified** unless marked.

## The publish gate

The workbook owner's standing rule, violated once under exactly the conditions
that feel like authorisation: being pointed at a production URL, being asked to
fix something there, and being given a deadline. None of those are permission.
Permission is two things, both typed by the user in the current conversation: an
explicit instruction naming production as the target, then a "yes" to your "Are
you sure?" that spells out that the production workbook will be overwritten. A
button click on a prompt is neither. Without both, the target is the
non-production project the user named for this build (ask before the first
publish; `GPA-monitor-temp`, `c74d8e08-b856-4430-a759-ebacb061e376`, when they
have no preference). A rollback is another production publish and needs the same
two confirmations. After a production publish, the user opens and checks the
production workbook themselves; no checker or render here can guarantee it is
not corrupted.

The gate has to run before the publish call: by the time `publish` returns, the
overwrite has already happened on the server, so a check on the returned item
can only report where it landed. Assert the literal project id and the review
name prefix on the request object, then keep the post-publish raise as
confirmation. A raise, not an assert: asserts are stripped under `-O`.

```python
if TEMP_PROJECT != "c74d8e08-b856-4430-a759-ebacb061e376":  # or the id the user named
    raise RuntimeError("target is not the agreed non-production project")
if not item.name.startswith("ZZ-REVIEW "):
    raise RuntimeError("review copies carry the ZZ-REVIEW prefix")
item = server.workbooks.publish(item, path, mode=tsc.Server.PublishMode.Overwrite)
if item.project_id != TEMP_PROJECT:
    raise RuntimeError(f"published to {item.project_name}, not the temp project")
```

Include the date in the review name so two sessions cannot overwrite each
other's copies. Across about a dozen Overwrites of the same target in #5230 the
LUID and `content_url` never changed (Verified), so an Overwrite lands on the
existing workbook; whether a different session's same-named workbook would be
matched is still Inferred ([unverified-warnings.md](unverified-warnings.md)).
The date costs nothing and closes the case either way.

## What a publish drops, and what to do about it

Verified in #5230 across 13 publishes on REST API 3.25 with
`tableauserverclient` 0.41, unless marked.

- **Hidden views.** `WorkbookItem.hidden_views` is write-only in the library: no
  read path populates it, so the server's hidden state cannot be read back off
  the item and a publish without the argument makes every publishable sheet a
  live view. In #5230 one workbook marked 20 sheets publishable against 10 live
  views, another 12 against 2. Compute the list to hide before the call: from
  the `.twb`'s `<windows>` element take entries whose `class` is `worksheet` or
  `dashboard` and whose `hidden` is not `'true'`; subtract the live view names
  of the **overwrite target** (not a scratch copy); subtract the sheets this
  edit deliberately added. `<worksheets>` and `<dashboards>` list every sheet
  whether publishable or not and are the wrong source. Pass the result as
  `hidden_views` on the `WorkbookItem`. Verified again on a second workbook: 15
  publishable minus 5 live gave 10 to hide, and the copy came up with exactly
  production's 5 live views.
- **Embedded connection credentials.** A publish without a `connections=[...]`
  list drops them. The scratch copy hides this because the packaged extract
  still renders; the owner sees a failing refresh or a credential prompt later.
  How to put them back is **not settled**: #5230 reports `update_connection`
  with `oauth = True`, but in the installed library `oauth` exists only on
  `ConnectionCredentials` and the request builder `update_connection` uses never
  emits it; the only path that does is `publish(connections=[...])`, which #5230
  saw report success on a live-connection workbook while leaving
  `embed_password` false (a value the library also returns when the server omits
  the attribute). Until a probe settles the call, say in the hand-over that
  credentials were not carried, and treat re-embedding a service account's
  credential as the owner's decision. Never write a key into a throwaway test
  file; the 1Password fixture in `tests/conftest.py` supplies secrets at run
  time.
- **Revision number.** Every Overwrite on this site created a revision (131 to
  132, 107 to 108, 45 to 46, 100 to 101). Call `populate_revisions` on the
  target before publishing and record the current number in the hand-over so the
  owner has a restore point they apply themselves from the Server UI.
  `revision_number` comes back as a string, so `max()` picks `"9"` over `"24"`;
  cast to `int` first (Verified). That is the owner's action, not yours: a
  restore on production is a production change and needs the same two
  confirmations as a publish.
- **Refresh schedules and permissions.** Not established. A refresh was already
  queued after several Overwrites, which suggests the schedule survived, but
  nobody listed tasks before and after; the probe in
  [unverified-warnings.md](unverified-warnings.md) is unchanged.

## Proving a row-level-security change

If the build touched a permissions calculation, a render as your own identity is
worthless when your token sits in an all-access group: the gate returns true for
every row and an applied gate looks identical to a broken one (Verified, #5230).
Publish a **probe build** with the all-access branch removed to the
non-production project, render it at the same crop, resolution and parameter
value as the control, and require both halves: rows scoped to another department
are **absent**, and rows for the render identity's own department are
**present**. Absence alone passes a build that renders nothing. The probe build
is a throwaway: it never becomes the hand-over, and you delete it from the
project when the check is done.

## Pull fresh, every time

The owner republished the workbook mid-project with a real design change buried
in a routine-looking save: a cross-datasource filter added to 17 sheets. Two
separate rebuilds were needed because of base drift. Download, record the
revision, and diff against your previous base before touching anything:

```python
wb = server.workbooks.get_by_id(WORKBOOK_LUID)
print(wb.project_name, wb.updated_at)
server.workbooks.download(WORKBOOK_LUID, filepath=str(out_dir / "base"),
                          include_extract=True)
```

Two traps in that call:

- **`tableauserverclient` appends the extension.** Passing
  `filepath=".../base.twbx"` produces `base.twbx.twbx`. Pass the stem and take
  the path the call returns.
- **`include_extract=True` matters.** Without it the download is a few hundred
  kilobytes instead of thirty megabytes, and republishing that strips the data.

Then diff the base against your last one:

```python
for label, pat in (("worksheets", r"<worksheet name='([^']*)'"),
                   ("parameters", r"name='(\[Parameter \d+\])'")):
    old, new = set(re.findall(pat, a)), set(re.findall(pat, b))
    print(label, sorted(old - new), sorted(new - old))
```

A pure extract refresh changes only `<datasources>`; worksheets and dashboards
stay byte-identical. Anything else is a design change to understand before
building on it. Between two pulls a day apart the base gained a sheet and a
tooltip sheet, swapped a logo asset, renumbered `<devicelayouts>` ids, un-hid a
window, and pointed `<repository-location>` at a `ZZ-REVIEW…` name: the owner
had promoted a review copy. The target dashboard's `<zones>` were
byte-identical, so the layout map survived; check that before reusing one.

Pass the fresh base, not the older pull, as `--ref` to `check_twb.py`. Against
an older pull, Tableau's own new elements (`preference`, `refresh`,
`refresh-event`) are reported as absent from the reference, which is noise. The
older pull as `--ref` answers one question only: what the owner changed.

## Write the assertion before the edit

For each change, write a script that asserts the finished state, run it against
the _unedited_ file, and confirm it fails. Then make it pass. Then build a
mutant of your own output that is subtly wrong and confirm the assertion catches
it. Assertions in the source project passed a duplicated zone, a re-parented
zone, a reordered zone and a card nested inside another card before mutation
testing found each hole.

`docs/tableau-xml/scripts/mutate.py` does the text surgery. Its `control` mode
must produce a byte-identical copy before any mutant result is meaningful; an
ElementTree round-trip fails this test because it rewrites attribute quoting and
line endings enough to break a regex-based assertion on an _unmutated_ file.

Resolve field references by caption at runtime rather than hard-coding instance
strings, so a transcription slip fails loudly instead of rendering a literal
token.

## Reading exit codes

Never through a pipeline. `cmd | tail` returns `tail`'s status; two exit codes
were misreported that way, one of them a SIGPIPE artifact reported as `120`.

```bash
uv run python docs/tableau-xml/scripts/check_twb.py out.twb >/tmp/o.out 2>&1; rc=$?
echo "[$rc] $(tail -1 /tmp/o.out)"
```

## Repack

A `.twb` is the XML; a `.twbx` is a zip of that XML plus the extracts. Rebuild
the archive by copying every entry from a donor `.twbx` and swapping only the
`.twb`. `docs/tableau-xml/scripts/repack.py` does this and then asserts the
packaged `.twb` is byte-identical to the source and that no bare LF appeared. An
earlier version flattened 27,000 CRLF endings on every repack and nobody
noticed, because the file on disk stayed correct. It does not check that the
donor is the `.twbx` your base came from; compare the donor's packaged `.twb`
against `base.twb` yourself, or an XML edited from one pull ships with another
pull's extract.

## Publish and render

The source project published with `show_tabs=True`. Whether that changed a
setting the owner had chosen was not probed; read `wb.show_tabs` off the
downloaded item and preserve it
([unverified-warnings.md](unverified-warnings.md)). Render with the parameter
set explicitly, so a parameter-dependent change can be seen both ways:

```python
opts = tsc.ImageRequestOptions(imageresolution=tsc.ImageRequestOptions.Resolution.High)
opts.parameter("GPA basis", "On the books today")
server.views.populate_image(view, opts)
```

Setting a parameter through the render API bypasses the domain check that a real
click performs. A render once "proved" a parameter action that was still broken.

## Look at the render

- A full 2732x1800 render may trip output scanning as high-entropy content. Crop
  to the region of interest and read the crop.
- Sample pixels to assert colour rather than eyeballing it:

  ```python
  crop = img.crop(box)
  counts = Counter(crop.getdata())
  # count pixels within tolerance of the expected hex
  ```

- A render **cannot** show a hover or a click. Tooltips, parameter actions and
  navigation buttons are unverifiable this way. Say so and ask a human rather
  than inferring from structure.

## Credentials in this repo

`docs/tableau-xml/scripts/tsc_session.py` is the download/publish/render
template. It runs as a throwaway pytest file because the autouse fixture in
`tests/conftest.py` loads secrets from 1Password; a plain `uv run python` gets
no credentials, and that failure reads like a missing account rather than a
missing fixture.

```bash
cp docs/tableau-xml/scripts/tsc_session.py tests/test_zz_tableau.py
# fill the three REPLACE-ME values
uv run pytest tests/test_zz_tableau.py -s
rm tests/test_zz_tableau.py
```

Copy the template with `cp` or the Write tool. A Bash heredoc that writes the
template's lines is denied by the PreToolUse hook: its credential lines match
the hook's patterns (Verified, one denied call).

## Sessions and jobs

Observed in #5230 on REST API 3.25 with `tableauserverclient` 0.41; library
facts checked against the installed source.

- **`401002: Invalid authentication credentials` mid-run.** Three run failures
  in #5230. The cause is not established: #5230 read it as one active session
  per token, while this repo's Dagster resource
  (`src/teamster/libraries/tableau/CLAUDE.md`) attributes the same code to a
  sign-in race and recovers with a fresh sign-in. The recovery is the same
  either way: hold one session, sign in through the `with` block the template
  already uses (it signs out on exit and on exception), poll a job with your own
  loop, and re-sign-in on `401002`. `wait_for_job` is a plain sleep-and-poll
  loop with no re-authentication and no timeout by default, so a session lost
  mid-poll surfaces as an error from its next request; write the loop yourself.
  Whether the Tableau MCP's token is the same one the template uses is
  unverified; if so, an MCP call during a publish is a plausible trigger.
- **`403180`, `Full extract refresh operation for the workbook is not allowed`,
  is not a credential failure.** The workbook has no extract; that is normal for
  a live connection. The two connection types need opposite proofs: a live
  connection cannot draw without a credential, so a render proves it; an
  extract-backed workbook renders from the `.hyper` regardless, so a render
  proves nothing and only a refresh counts.
- **`jobs.get_by_id` on a `create_extract` job returns server code `400031`**
  (`REST API does not support background job type :create_extracts`). The
  jobs-list endpoint (`jobs.get()`, `jobs.filter()`) was not tried and may poll
  it; until then, watch the workbook's size.
- **`jobs.get()` with no id returns a tuple** of a `BackgroundJobItem` list and
  a `PaginationItem`. `BackgroundJobItem` has `title`, `subtitle`, `status`,
  `ended_at`; it has no `workbook_name`, `finish_code`, or `completed_at`, so
  filtering on `workbook_name` raises `AttributeError`.
- **`populate_csv` on a dashboard returned 0 rows, and so did the control.**
  Export from a worksheet, or render and read the image. The lesson is in
  [failure-catalog.md](failure-catalog.md): the test was wrong before the
  workbook was.

## Cross-workbook merges lose things silently

Merging one workbook into another dropped content with no warning in either
direction:

- **A parameter collided and was deleted.** Most collisions were resolved by
  renaming (`Selected school` became `[Parameter 2 1]`), but one boolean was
  simply removed while every reference to it survived. Two actions and a
  visibility node kept pointing at an id that now belonged to an unrelated
  string parameter, so a pop-out could never open and every click silently
  overwrote the other parameter's value.
- **A worksheet used only as a viz-in-tooltip was deleted** while both
  references to it were kept, breaking the tooltips that depended on it.

After any merge, diff the worksheet list **and** the parameter list against both
sources before publishing. In this corpus Tableau renamed on some collisions and
content disappeared on others, with no report either way; whether the second
case was a deletion or a merge on name and datatype is unverified
([unverified-warnings.md](unverified-warnings.md)).

## Adjacent tooling, not verified here

**Inferred**, from reading the files, never from a render or a Desktop open. The
`tableau-dashboard-plugin` (skills `tableau-build`, `tableau-spec`, and
siblings) generates new workbooks from a spec; it is the tool for building from
scratch, not for editing an existing workbook. Two of its files may be useful
inputs to a probe, on the same terms as anything else found in a file:

- `skills/tableau-build/scripts/validate_twb_xsd.py` validates a `.twb` against
  the Tableau 2026.1 XSD from `tableau/tableau-document-schemas` and needs
  `lxml`. The XSD marks content sections `processContents="skip"`, and the
  source project's defects passed a schema check, so treat a pass as one more
  checker, not as Desktop.
- `skill/tableau-dashboard-creator/references/snippets/worksheets/custom-tooltip.twb`
  carries a `<customized-tooltip>` in form A with `Æ&#9;` runs between label and
  value. That contradicts the corpus observation that tooltips carried no `Æ`
  sentinel ([formatting.md](formatting.md)); the contradiction is unresolved and
  is one more reason to probe this file rather than copy it. Presence in a file
  is not evidence of rendering.
