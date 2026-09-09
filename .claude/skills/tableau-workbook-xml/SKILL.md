---
name: tableau-workbook-xml
description:
  "Use when editing a Tableau workbook as XML: hand-editing a .twb or .twbx,
  adding tooltips, titles, captions or mark-label text, restructuring dashboard
  zones, changing number formats, moving an element between workbooks, or
  debugging a workbook that publishes to Server but Desktop refuses to open (`no
  declaration found for element`, `missing elements in content model`, `not
  allowed for content model`, `D2E8DA72`). Also when a render shows blank or
  literal placeholder text, `####`, a clipped caption, or overlapping zones."
---

# tableau-workbook-xml

Everything here was learned by editing one production workbook as `.twb` XML,
publishing to a scratch project, and rendering. Claims are marked **Verified**
(seen in a render or a Desktop error) or **Inferred** (consistent with a working
file, never rendered). Two inferences in the source project were wrong, and both
had the same shape: structural similarity treated as behavioral proof. A
parameter token resolved in a worksheet title, so it was assumed to resolve in a
mark label; it renders blank there. A tooltip form was present in the workbook,
so it was assumed to render; the copy printed its tokens literally. When you
find yourself reasoning "this works there, so it works here", probe instead.

## Three rules

1. **A passing checker is not a working dashboard.** Every serious defect in the
   source project passed XML validation, a schema check, and publish to Server.
   Four defects in one build survived nine mutation tests and were found only in
   the rendered image. Render and look. Where a behavior cannot be rendered (a
   hover, a click), say so out loud rather than inferring it.
2. **Desktop and Server disagree about validity.** Server is permissive and
   rendered workbooks Desktop refused to open. A successful publish proves
   nothing about Desktop. `check_twb.py` exists because each of its checks is a
   Desktop refusal that Server waved through.
3. **The tests are more likely wrong than the edits.** Nearly every serious
   review finding in the source project was against a test that would have
   passed something broken: a geometry checker with 4,500 units of tolerance
   against a 4,445-unit bug, a structure assertion that passed a duplicated, a
   re-parented, and a reordered zone. When an assertion passes, ask what broken
   input it would also pass, build that input with `mutate.py`, and run it.

## The loop

Scripts live in `docs/tableau-xml/scripts/`. Run them all, every time; read exit
codes with a redirect, never through a pipe (`cmd >/tmp/o 2>&1; rc=$?`).

1. **Pull fresh.** Download with `include_extract=True`, record `updated_at`,
   and diff the worksheet and parameter lists against your last base. The owner
   republished mid-project with a 17-sheet change buried in a routine save.
   Code: [references/build-workflow.md](references/build-workflow.md).
2. **Write the assertion before the edit.** Run it against the unedited file and
   confirm it fails. Then, once it passes, build a mutant of your output with
   `mutate.py` and confirm the assertion catches it. Run `control` first; it
   must be byte-identical or every mutant result is void.
3. **Edit** with `encoding="utf-8", newline=""` on both read and write. Anchor
   every substitution and assert it matched exactly once. Assert output length
   is within 20% of input. Parse with `ET.fromstring` before writing. Edit the
   dashboard's `<zones>` block, never `<devicelayouts>`. Insert into the feature
   manifest; never regenerate it. Traps:
   [references/formatting.md](references/formatting.md).
4. **Check.**

   ```bash
   uv run python docs/tableau-xml/scripts/check_twb.py out.twb --ref base.twb
   uv run python docs/tableau-xml/scripts/check_geometry.py out.twb "Dashboard Name" --baseline base.twb
   ```

   Always pass `--ref` and `--baseline`. Without them the manifest-drop check is
   skipped and the geometry check falls back to a bound that passed a real
   defect.

5. **Repack** with `repack.py`. It swaps only the `.twb` into a donor `.twbx`
   and asserts the packaged bytes match the source with zero bare LF.
6. **Publish to a scratch project** (`GPA-monitor-temp`; id in the root
   CLAUDE.md _Never_ block). Raise on `item.project_id != TEMP_PROJECT`
   immediately after the publish call. A production URL, a request to fix
   production, and a deadline are not authorisation. The only thing that lifts
   this is the user's own message, in the moment, naming production as the
   target, followed by a second confirmation after you ask "Are you sure? This
   overwrites the production workbook and is visible to the whole network." Both
   must be the user's words in this session, not an inference from context.
   Rolling a bad production publish back is also a production publish and needs
   the same two confirmations. After any production publish, tell the user to
   open the production workbook themselves and check it: nothing in this skill
   can guarantee the published workbook is not corrupted.
7. **Render and look.** Render with each parameter value set explicitly. Crop
   before reading. A render cannot show a hover or a click: tooltips, parameter
   actions and navigation buttons need a human, and a render-API parameter set
   bypasses the domain check a real click performs.
8. **Hand over** the `.twbx` plus the scratch copy. Report what was verified,
   what was inferred, and what still needs a human hover or click.

Credentialed steps (1, 6, 7) run as a throwaway `tests/test_zz_*.py` under
`uv run pytest -s`, copied from `tsc_session.py`; a plain `uv run python` gets
no secrets.

## By symptom

Desktop refusals (Server accepted every one first). Detail and the manifest
table: [references/content-models.md](references/content-models.md).

- **`element 'reference-line' is not allowed for content model` (`D2E8DA72`).**
  Your `<customized-tooltip>` sits before that sheet's `<reference-line>`. Pane
  order is
  `view, mark, mark-sizing?, encodings?, label-data*, dropline?, trendline?, reference-line, customized-tooltip, customized-label, style`.
  Move it after the last of those that exist on that sheet; anchoring on
  `</encodings>` works until a sheet has a reference line. Run `check_twb.py`
  (its `check_pane_order` covers every worksheet in one pass and needs no
  `--ref`), then repack, publish to scratch, render.
- **`no declaration found for element 'x'`.** The feature manifest does not
  declare `x`. Insert the entry; never rebuild the manifest.
- **`missing elements in content model`.** A hand-built worksheet lacks
  `<simple-id>`, or its `<view>` lacks `<aggregation>`. Clone the skeleton from
  a working sheet.
- **`attribute 'user-specific' is not declared for element 'extract'`.** A
  manifest rebuild dropped the dotted
  `_.fcp.VConnDownstreamExtractsWithWarnings...` entry. `check_twb.py --ref`
  catches it.

Renders blank or literal. Matrix and probe examples:
[references/dynamic-text.md](references/dynamic-text.md).

- **Title renders nothing, no error.** The zone has `show-title='false'`. Flip
  it in `<zones>`.
- **Mark label has a blank line, or vanishes entirely.** A parameter token in
  `<customized-label>` renders blank (Verified); a calc on the Text shelf
  displaces the whole label. Use static text or the title surface.
- **Tooltip prints raw `[federated…].[usr:…:qk]`.** **Open question.** Two
  encodings exist: form A, the whole line in one CDATA run, and form B, the
  instance alone in a bare run with `<` and `>` split into neighbouring runs.
  Both are present in working sheets; a hand-built copy of form A printed its
  tokens literally, and form B was never hover-confirmed. Copy a working
  tooltip's runs verbatim, keeping run attributes and separator text, and swap
  only the `[datasource].[instance]` strings. A render cannot show a hover; ask
  a human.
- **Text in a dashboard text zone does not resolve.** It never does (Verified).
  Move it to a worksheet title or caption.

Layout. Numbers and the card idiom:
[references/layout-and-zones.md](references/layout-and-zones.md).

- **`####`.** Text does not fit. Remove a line; growing the box 66→78→88px did
  not help.
- **Caption truncates with an ellipsis.** Strips clip, they do not wrap. Budget
  is about `97 * width / 39676` characters; shorten.
- **Legend shows some of its entries.** Height, not width: 40px fits one swatch
  row, 70px fits two.
- **Two zones overlap.** A zone at the wrong nesting depth; valid XML, no error.
  `check_geometry.py --baseline`.
- **Percent-of-total axis reads 200%.** A `<lod>` on Detail changed the mark
  grain. Put the field on Tooltip.

Formats and edits. [references/formatting.md](references/formatting.md).

- **Need a number format.** `default-format` on the `<column>`; families in the
  reference. Table calcs cannot be formatted this way (not solved): hand to
  Desktop.
- **Parameter action fires, nothing changes.** A blanket replace rewrote the
  `<member>` domain. Every substitution asserts one match.

Process. [references/build-workflow.md](references/build-workflow.md) and
[references/failure-catalog.md](references/failure-catalog.md).

- **After a cross-workbook merge.** Diff worksheet and parameter lists against
  both sources. Tableau deletes on collision and reports nothing.
- **Whole-file diff, `.twbx.twbx`, tiny download, wrong exit code.** CRLF
  flattened by `read_text`; `filepath` gets an extension appended;
  `include_extract=False`; status read through a pipe.

Everything observed, with exact error strings and numbers:
[references/failure-catalog.md](references/failure-catalog.md).

## Scripts

All in `docs/tableau-xml/scripts/`; the README there has per-check tables.

- **`check_twb.py`**: `uv run python check_twb.py <twb> --ref <base.twb>`.
  Catches the six Desktop refusals across every worksheet in one pass: missing
  `<simple-id>`, undeclared feature for an element, `<view>` without
  `<aggregation>`, pane children out of model order, and with `--ref` manifest
  entries lost and elements absent from the reference.
- **`check_geometry.py`**:
  `uv run python check_geometry.py <twb> "<dashboard>" --baseline <base.twb>`.
  Catches sibling zones that overlap, a flow container whose
  parent-minus-children gap differs from the baseline's, and a top-level zone
  not spanning the canvas. Prints which mode it ran in.
- **`mutate.py`**:
  `uv run python mutate.py <src> <out> "<dashboard>" <op> [args]`. Catches
  nothing by itself; it builds a broken copy (`duplicate`, `reparent`,
  `move-after`, `swap`, `set-attr`, `set-format`, `delete`) so you can prove an
  assertion fails. Run `control` first.
- **`repack.py`**:
  `uv run python repack.py <edited.twb> <donor.twbx> <out.twbx>`. Catches CRLF
  flattened inside the archive and a packaged `.twb` differing from disk.
- **`tsc_session.py`**: copy to `tests/test_zz_*.py`, fill the three
  `REPLACE-ME` values, `uv run pytest -s`. Catches nothing; it is the download,
  publish-with-gate, and render template.

## Probing a surface

When a token, element, or form has not been rendered on the exact surface you
are editing: edit one sheet with a literal `PROBE ` marker, repack, publish to
scratch, render with the parameter set each way, and read the image for both the
marker and the value. The verified matrix of which surfaces resolve field and
parameter tokens is in [references/dynamic-text.md](references/dynamic-text.md).

## Not this skill

Building a new workbook from a spec is the `tableau-dashboard-plugin`
(`tableau-build`), which generates XML rather than editing it. Its XSD validator
and snippet files are listed as unverified inputs at the end of
[references/build-workflow.md](references/build-workflow.md).
