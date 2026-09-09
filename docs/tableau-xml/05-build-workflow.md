# The build workflow

The loop that works: pull fresh, assert first, edit, verify, repack, publish to
a scratch project, render, look. Each step below exists because skipping it cost
something.

## Never publish to production

The workbook owner's standing rule, and it was violated once in this project
under exactly the conditions that feel like authorisation: being pointed at a
production URL, being asked to fix something there, and being given a deadline.
None of those are permission.

Publish to a scratch project, verify, and hand over the package. Rolling a bad
production publish back is itself a production publish and belongs to the owner.

Put the gate in the code, before anything else happens:

```python
item = server.workbooks.publish(item, path, mode=tsc.Server.PublishMode.Overwrite)
assert item.project_id == TEMP_PROJECT, f"published to {item.project_name}!"
```

## Step 1: pull fresh, every time

**Verified.** The owner republished the workbook mid-project with a real design
change buried in a routine-looking save — a cross-datasource filter added to 17
sheets. A package built on a stale base would have destroyed it. Two separate
rebuilds were needed because of base drift.

Download, record the revision, and diff against your previous base before
touching anything:

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

Then diff the base against your last one — worksheet list, parameter list, and
any structure you rely on:

```python
for label, pat in (("worksheets", r"<worksheet name='([^']*)'"),
                   ("parameters", r"name='(\[Parameter \d+\])'")):
    old, new = set(re.findall(pat, a)), set(re.findall(pat, b))
    print(label, sorted(old - new), sorted(new - old))
```

A pure extract refresh changes only `<datasources>`; worksheets and dashboards
stay byte-identical. Anything else is a design change to understand before
building on it.

## Step 2: write the assertion before the edit

**This is the highest-value habit in the whole workflow.** For each change,
write a script that asserts the finished state, run it against the _unedited_
file, and confirm it fails. A test that has never failed proves nothing.

Then make it pass. Then — and this is the part usually skipped — build a mutant
of your own output that is subtly wrong and confirm the assertion catches it.
Assertions in this project passed a duplicated zone, a re-parented zone, a
reordered zone and a card nested inside another card before mutation testing
found each hole.

`scripts/mutate.py` does the text surgery for that. Its control mode must
produce a byte-identical copy before any mutant result is meaningful; an
ElementTree round-trip fails this test, because it rewrites attribute quoting
and line endings enough to break a regex-based assertion on an _unmutated_ file.

## Step 3: edit

Rules that earned their place, detailed in [04-formatting.md](04-formatting.md):

- Read and write with `encoding="utf-8", newline=""`.
- Every substitution anchored, asserting exactly one match.
- Assert output length is within 20% of input.
- Parse with `ET.fromstring` before writing.
- Operate on the dashboard's `<zones>` block, not `<devicelayouts>`.

Resolve field references by caption at runtime rather than hard-coding instance
strings, so a transcription slip fails loudly instead of rendering a literal
token.

## Step 4: verify locally

Run everything, every time. See [scripts/](scripts/).

```bash
uv run python check_twb.py out.twb --ref base.twb
uv run python check_geometry.py out.twb "Dashboard Name" --baseline base.twb
```

Read exit codes with a redirect, never through a pipeline. `cmd | tail` returns
`tail`'s status; two exit codes were misreported that way in this project, one
of them a SIGPIPE artifact reported as `120`.

```bash
uv run python check_twb.py out.twb >/tmp/o.out 2>&1; rc=$?
```

## Step 5: repack

A `.twb` is the XML; a `.twbx` is a zip of that XML plus the extracts. Rebuild
the archive by copying every entry from a donor `.twbx` and swapping only the
`.twb`:

```python
with zipfile.ZipFile(donor) as z:
    payloads = [(i, z.read(i.filename)) for i in z.infolist()]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z2:
    for i, data in payloads:
        z2.writestr(i, twb_bytes if i.filename.endswith(".twb") else data)
```

Verify the packaged `.twb` is byte-identical to the source on disk. The repack
helper in this project silently flattened CRLF for weeks because nobody checked.

## Step 6: publish and render

Publish with `show_tabs=True` unless told otherwise, and assert the project id
before doing anything else.

Render with the parameter set explicitly, so a parameter-dependent change can be
seen both ways:

```python
opts = tsc.ImageRequestOptions(imageresolution=tsc.ImageRequestOptions.Resolution.High)
opts.parameter("GPA basis", "On the books today")
server.views.populate_image(view, opts)
```

## Step 7: look at the render

Not optional, and not a formality. Four defects in one build reached this step
having passed every structural check.

Practical notes:

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
- Setting a parameter through the render API bypasses the domain check that a
  real click performs. A render once "proved" a parameter action that was still
  broken.

## Step 8: hand over

The deliverable is a `.twbx` plus a review copy in the scratch project. Report
what was verified, what was inferred, and what needs a human hover or click.

## Cross-workbook merges lose things silently

**Verified.** Merging one workbook into another dropped content with no warning
in either direction:

- **A parameter collided and was deleted.** Most collisions were resolved by
  renaming (`Selected school` became `[Parameter 2 1]`), but one boolean was
  simply removed while every reference to it survived. Two actions and a
  visibility node kept pointing at an id that now belonged to an unrelated
  string parameter, so a pop-out could never open and every click silently
  overwrote the other parameter's value.
- **A worksheet used only as a viz-in-tooltip was deleted** while both
  references to it were kept, breaking the tooltips that depended on it.

After any merge, diff the worksheet list **and** the parameter list against both
sources before publishing. Tableau renames on collision when it can and deletes
when it cannot, and reports neither.
