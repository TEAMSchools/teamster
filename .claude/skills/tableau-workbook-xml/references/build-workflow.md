# Build workflow: code detail

The step order lives in `SKILL.md`. This file holds the code behind each step
and the traps each snippet guards. All claims are **Verified** unless marked.

## The publish gate

The workbook owner's standing rule, violated once under exactly the conditions
that feel like authorisation: being pointed at a production URL, being asked to
fix something there, and being given a deadline. None of those are permission.
Permission is two things, both in the user's own words in the current session:
an explicit instruction naming production as the target, then a "yes" to your
"Are you sure?" that spells out that the production workbook will be
overwritten. Without both, the target is the scratch project. After a production
publish, the user opens and checks the production workbook themselves; no
checker or render here can guarantee it is not corrupted. Put the gate in the
code, immediately after the publish call and before any render or populate. A
raise, not an assert: asserts are stripped under `-O`.

```python
item = server.workbooks.publish(item, path, mode=tsc.Server.PublishMode.Overwrite)
if item.project_id != TEMP_PROJECT:
    raise RuntimeError(f"published to {item.project_name}, not the temp project")
```

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
building on it.

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
noticed, because the file on disk stayed correct.

## Publish and render

Publish with `show_tabs=True` unless told otherwise. Render with the parameter
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
sources before publishing. Tableau renames on collision when it can and deletes
when it cannot, and reports neither.

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
  value. Presence in a file is not evidence of rendering; it is a candidate to
  probe, not an answer to the open tooltip question.
