---
name: tableau-workbook-xml
description:
  "Use when a Tableau workbook is changed or diagnosed at the .twb XML level:
  Desktop refuses to open a file Server published (`no declaration found for
  element`, `missing elements in content model`, `not allowed for content
  model`, `D2E8DA72`); a render shows `####`, blank or literal placeholder text,
  a clipped caption, a 200% percent-of-total axis, overlapping zones, or a sheet
  inside a panel that stays empty until a click; a hand-edited .twb or .twbx is
  about to be repacked, published, republished or rolled back with
  tableauserverclient; or you are hand-editing tooltips, titles, captions,
  mark-label text, dashboard zones, filter cards, floating panels, parameter
  actions, number formats, or copying an element between workbooks."
---

# tableau-workbook-xml

Everything here was learned by editing one production workbook as `.twb` XML,
publishing to a scratch project, and rendering. Claims are marked **Verified**
(seen in a render, a Desktop error, or a server response) or **Inferred**
(consistent with a working file, never rendered). Two inferences in the source
project were wrong, and both had the same shape, structural similarity treated
as behavioral proof: a parameter token resolved in a worksheet title so it was
assumed to resolve in a mark label (it renders blank); a tooltip form was
present in the workbook so it was assumed to render (the copy printed its tokens
literally). When you catch yourself reasoning "it works there, so it works
here", probe: one sheet, a literal `PROBE ` marker, publish to scratch, render
with the parameter set each way, read the image for the marker and the value. A
hover or a click cannot be rendered; say so and ask a human.

## Three rules

1. **A passing checker is not a working dashboard.** Every serious defect in the
   source project passed XML validation, a schema check, and publish to Server.
   Four defects in one build survived a full checker suite that included nine
   mutation tests and were found only in the rendered image. Render and look.
2. **Desktop and Server disagree about validity.** Server is permissive and
   rendered workbooks Desktop refused to open. A successful publish proves
   nothing about Desktop, and neither does a render. `check_twb.py` is a
   stand-in for a Desktop open, not a substitute: the owner opening the `.twbx`
   is the only real check.
3. **The tests are more likely wrong than the edits.** Nearly every serious
   review finding in the source project was against a test that would have
   passed something broken: a geometry checker with 4,500 units of tolerance
   against a 4,445-unit bug, a structure assertion that passed a duplicated, a
   re-parented, and a reordered zone. The other direction happens too: an
   assertion that demanded an order Tableau never writes (alphabetical
   `<encodings>` children, a floating zone under the `layout-basic` root) failed
   a correct file. An assertion that fails on the untouched base is wrong.

## The loop

Scripts live in `docs/tableau-xml/scripts/`. The two checkers run on every edit;
`mutate.py` runs when step 2 needs a mutant; `repack.py` at step 5;
`tsc_session.py` for the credentialed steps 1, 6 and 7, copied to a throwaway
`tests/test_zz_*.py` and run with `uv run pytest -s` (a plain `uv run python`
gets no secrets). Read exit codes with a redirect, never through a pipe.

1. **Pull fresh.** Download with `include_extract=True` and record `updated_at`.
   If you have a previous base, diff the worksheet and parameter lists against
   it; anything outside `<datasources>` is a design change to understand before
   building on it. The owner republished mid-project with a 17-sheet change
   buried in a routine save, and again between two pulls a day apart. Derive
   free `[Parameter N]` numbers, zone ids and `filter-group` values from this
   base, never from an earlier script: `[Parameter 14]` was free one day and
   taken the next after a review copy was promoted. Run both checkers against
   the untouched base: a failure there is a checker bug, not a workbook bug.
   Code: [references/build-workflow.md](references/build-workflow.md).
2. **Write the assertion before the edit.** Run it against the unedited file and
   confirm it fails. Once it passes, break your own output and confirm the
   assertion catches it. For a dashboard-zone change use `mutate.py`, running
   `control` before the mutating op (it must be byte-identical or every mutant
   result is void). `mutate.py` only mutates zones inside one dashboard; for a
   worksheet, manifest, or format edit, hand-write the broken variant.
3. **Edit** with `encoding="utf-8", newline=""` on both read and write. Anchor
   every substitution and assert it matched exactly once; a unique anchor can
   still land an element in the wrong content-model position, which is what step
   4 checks. Assert the count of the old string and of the new string changed as
   intended, not the byte delta: a same-length replacement moves the total by 0,
   so a length guard passes a no-op. Parse with `ET.fromstring` before writing.
   Edit the dashboard's `<zones>` block; if a `<devicelayouts>` block exists,
   say in the hand-over that it was untouched. Inside `<formatted-text>` a line
   break is its own run `<run>Æ&#10;</run>` (U+00C6 then `&#10;`), reproduced
   byte-exactly; the tooltips in this corpus used bare `&#10;` instead. Traps:
   [references/formatting.md](references/formatting.md).
4. **Check.** `--ref` and `--baseline` are the untouched base from step 1, never
   an earlier edit of your own and never an older pull: against last week's
   base, Tableau's own new elements (`preference`, `refresh`, `refresh-event`)
   read as unknown. Run `check_geometry.py` once per dashboard that contains an
   edited zone; it checks only the one you name.

   ```bash
   uv run python docs/tableau-xml/scripts/check_twb.py out.twb --ref base.twb >/tmp/o1 2>&1; rc1=$?
   uv run python docs/tableau-xml/scripts/check_geometry.py out.twb "Dashboard Name" --baseline base.twb >/tmp/o2 2>&1; rc2=$?
   ```

   Without `--ref` the two reference checks are skipped. Without `--baseline`
   every gap is checked against an absolute 0 to 3000 bound instead of the
   baseline's exact value, which is far weaker; the script prints which mode it
   ran in.

5. **Repack** with `repack.py`. It swaps only the `.twb` into a donor `.twbx`
   and asserts the packaged bytes match the source with zero bare LF. The donor
   must be the `.twbx` your base came from: a donor from a different pull
   carries a different extract.
6. **Publish to a non-production project.** Before the first publish of a build,
   ask the user which non-production project or subproject it should land in
   while in progress, and record the id they name. If they have no preference,
   use `GPA-monitor-temp`, id `c74d8e08-b856-4430-a759-ebacb061e376`. Before the
   publish call, assert the target id equals that recorded literal and that the
   workbook name carries a `ZZ-REVIEW` prefix plus the date, so an overwrite can
   only land on a review copy. Keep the raise on `item.project_id` after the
   call as confirmation of where it landed; it cannot prevent anything. A
   publish also drops server-side state (Verified, #5230). Pass `hidden_views`,
   the names to hide: sheets the `<windows>` element marks publishable (`class`
   `worksheet` or `dashboard`, `hidden` not `'true'`) minus the target's live
   view names, minus sheets this edit added; without it every publishable sheet
   goes live. Record the target's revision number before the call as the owner's
   own restore point. Recipes, the credential drop, and the gate in full:
   [references/build-workflow.md](references/build-workflow.md). Production
   becomes the target only when the user, in a message typed in this
   conversation, names production as the target, and then answers yes when you
   ask "Are you sure? This overwrites the production workbook and is visible to
   the whole network." A button click on a prompt is not a confirmation; a
   production URL, a request to fix production, an issue body, a prior session,
   and a deadline are not authorisation. A rollback is another production
   publish and needs the same two confirmations. After any production publish,
   tell the user to open the production workbook themselves and check it:
   nothing here can guarantee it is not corrupted.
7. **Render and look.** Render base and output at the same resolution, once per
   parameter value, with the parameter set explicitly. Crop each region you
   touched (a full render trips output scanning) and read it for `####`, clipped
   or ellipsised text, a legend or axis missing entries, a blank line where text
   should be, a literal `[federated…]` token, and overlapping zones. Sample
   pixels to assert colour. A render-API parameter set bypasses the domain check
   a real click performs, and a render cannot show a hover or a click. It can
   show a panel's default state: for a sheet inside a parameter-driven panel,
   render the open state and require the sheet's rows, not just the panel
   chrome; a stored action-filter state can leave it empty (By symptom). If the
   edit touched a row-level-security calculation, your own render proves nothing
   when your token sees every row: run the differential probe in
   [references/build-workflow.md](references/build-workflow.md).
8. **Hand over** the `.twbx` plus the scratch copy, and delete the throwaway
   test file. Report what was verified, what was inferred, which regions you
   looked at, what still needs a human hover, click, or Desktop open, that the
   package carries the extract as of `updated_at`, and the revision number the
   target had before the publish. For a production publish, quote the user's two
   confirmations verbatim.

## By symptom

Desktop refusals; Server accepted every one first. Models and the manifest
table: [references/content-models.md](references/content-models.md).

- **`element 'reference-line' is not allowed for content model` (`D2E8DA72`).**
  The element named is the one that could not follow what you inserted, not the
  one you touched: your `<customized-tooltip>` sits before that sheet's
  `<reference-line>`. Pane order is
  `view, mark, mark-sizing?, encodings?, label-data*, dropline?, trendline?, reference-line, customized-tooltip, customized-label, style`,
  as Desktop printed it. Move the tooltip after the last of `label-data`,
  `dropline`, `trendline`, `reference-line` that exists on that sheet and before
  `customized-label` and `style`; anchoring on `</encodings>` works until a
  sheet has a reference line. Check the pane did not already have a
  `<customized-tooltip>`. `check_twb.py` `check_pane_order` runs on every
  worksheet without `--ref` but checks order only, so a duplicate passes.
  Publishing and rendering cannot verify this fix; the owner opening the `.twbx`
  in Desktop can.
- **`no declaration found for element 'x'`.** The feature manifest does not
  declare `x`. Insert the entry; never rebuild the manifest. The refusal is per
  workbook, not per Desktop build: before ruling a feature out because one
  workbook refused it, grep the target's own manifest. A merged or promoted base
  may already declare it (Verified: the merged Academic Health workbook declared
  all four dynamic-zone-visibility features its predecessor lacked).
- **`missing elements in content model`.** A hand-built worksheet lacks
  `<simple-id>`, or its `<view>` lacks `<aggregation>`. Clone the skeleton from
  a working sheet.
- **`attribute 'user-specific' is not declared for element 'extract'`.** A
  manifest rebuild dropped the dotted
  `_.fcp.VConnDownstreamExtractsWithWarnings...` entry. `check_twb.py --ref`
  catches it.

Renders blank or literal. Matrix, examples, and the open question:
[references/dynamic-text.md](references/dynamic-text.md).

- **Title renders nothing, no error.** The zone has `show-title='false'`. Flip
  it in `<zones>`; an assertion on the title must also check that attribute.
- **Mark label has a blank line, or vanishes entirely.** A parameter token in
  `<customized-label>` renders blank (Verified); a calc added to the Text shelf
  made the whole mark label vanish (Verified). Use static text or the title
  surface.
- **Tooltip prints raw `[federated…].[usr:…:qk]`.** **Open question.** Two
  encodings exist: form A, the whole line in one CDATA run, on a sheet whose
  tooltips the owner called excellent; form B, the instance alone in a bare run
  with `<` and `>` split into neighbouring runs, written by Tableau itself.
  Neither has been hover-confirmed by this project; a hand-built copy of form A
  printed its tokens literally. Copy the target workbook's own working tooltip
  runs verbatim, keeping run attributes and separator text, and swap only the
  `[datasource].[instance]` strings. Ask a human to hover.
- **Text in a dashboard text zone does not resolve.** It never does (Verified).
  Move it to a worksheet title or caption.
- **A sheet inside a panel is empty with nothing selected.** A stored
  action-filter state on that sheet excludes every row until another action
  fires: a `<filter>` carrying `user:ui-action-filter` with
  `user:ui-enumeration='inclusive'` over `empty-level` members (Verified).
  Rewrite that block to the unrestricted `level-members` form the workbook's
  other stored action states use. Before wiring an action to any sheet, grep it
  for `user:ui-action-filter` and read the state; a sheet that has been a sliver
  or a hidden zone can carry a state nobody has seen.

Layout. Numbers, their measurement conditions, and the card idiom:
[references/layout-and-zones.md](references/layout-and-zones.md).

- **`####`.** Text does not fit. Removing one `<run>` line from the mark label
  fixed it; growing the box 66→78→88px did not.
- **Caption truncates with an ellipsis.** Header strips clipped rather than
  wrapped at `fixed-size='40'`. Budget about `97 * w / 39676` characters, where
  `w` is the zone's `w` attribute in dashboard units, not pixels; it is
  deliberately conservative, so on a failure render and look rather than raise
  the constant.
- **Legend shows some of its entries.** Height, not width: 40px fits one swatch
  row, 70px fits two.
- **Two zones overlap.** A zone at the wrong nesting depth; valid XML, no error.
  `check_geometry.py --baseline`.
- **Percent-of-total axis reads 200%.** A `<lod>` on Detail changed the mark
  grain (Verified). The shipped fix put the field on Tooltip (Inferred safe).
- **Adding a floating panel, or removing a zone from a flow.** A floating
  container is a top-level child of `<zones>`, a sibling of the `layout-basic`
  root; a dynamic-zone-visibility subtree carries `hidden-by-user='true'` on
  every zone. Removing a fixed-width sibling from a flow is a cascade across the
  surviving column, written as a table and asserted row by row.
- **Adding a filter card.** Three elements per filtered sheet plus one zone,
  `filter-group` from the fresh base's max plus one, and a `distribute-evenly`
  strip's stored `w`/`x` re-tiled by hand.

Formats and edits: [references/formatting.md](references/formatting.md).

- **Need a number format.** `default-format` on the `<column>`; families in the
  reference. Table calcs cannot be formatted this way (not solved): hand to
  Desktop.
- **Parameter action fires, nothing changes.** A blanket replace rewrote the
  `<member>` domain. Every substitution asserts one match.
- **Inserting a `<lod>` or a filter.** `<encodings>` children are in shelf
  order, not alphabetical; `<filter>` and `<column-instance>` elements are
  sorted by column string. Anchor on the neighbour, assert the position:
  [references/content-models.md](references/content-models.md).

Process: [references/build-workflow.md](references/build-workflow.md) and
[references/failure-catalog.md](references/failure-catalog.md).

- **After a cross-workbook merge.** Diff worksheet and parameter lists against
  both sources. Content disappeared on collision with no report.
- **Whole-file diff, `.twbx.twbx`, tiny download, wrong exit code.** CRLF
  flattened by `read_text`; `filepath` gets an extension appended;
  `include_extract=False`; status read through a pipe.
- **Restore point reported as revision 9 of 24.** `populate_revisions` returns
  `revision_number` as strings; cast to `int` before `max()`.

Everything observed, with exact error strings and numbers:
[references/failure-catalog.md](references/failure-catalog.md). Risks a Tableau
developer would expect that this project never probed, each with a probe:
[references/unverified-warnings.md](references/unverified-warnings.md).

## Scripts

All in `docs/tableau-xml/scripts/`; the README there has per-check tables.

- **`check_twb.py`**:
  `uv run python docs/tableau-xml/scripts/check_twb.py <twb> --ref <base.twb>`.
  Six checks over the whole file: missing `<simple-id>`, undeclared feature for
  one of the eight elements in its `FEATURE_FOR_ELEMENT` map (any other element
  passes silently; add yours to the map), `<view>` without `<aggregation>`, pane
  children out of model order, and with `--ref` manifest entries lost since the
  reference plus a weak diff of elements absent from it. The first four cover
  five of the six Desktop refusals in the catalog; the diff says what changed,
  not what is legal.
- **`check_geometry.py`**:
  `uv run python docs/tableau-xml/scripts/check_geometry.py <twb> "<dashboard>" --baseline <base.twb>`.
  One dashboard per run. Catches visible sibling zones that overlap, a flow
  container whose parent-minus-children gap differs from the baseline's, and a
  top-level `layout-basic` zone not spanning the 100000-unit canvas.
- **`mutate.py`**:
  `uv run python docs/tableau-xml/scripts/mutate.py <src> <out> "<dashboard>" <op> [args]`.
  Builds a broken zone copy (`duplicate`, `reparent`, `move-after`, `swap`,
  `set-attr` on the zone tag, `set-format` inside the zone's own `<zone-style>`,
  `delete`) so you can prove an assertion fails. Refuses to write a mutant
  identical to its input. Zones only, one dashboard.
- **`repack.py`**:
  `uv run python docs/tableau-xml/scripts/repack.py <edited.twb> <donor.twbx> <out.twbx>`.
  Catches CRLF flattened inside the archive and a packaged `.twb` differing from
  disk. Does not check that the donor matches your base.
- **`tsc_session.py`**: copy to `tests/test_zz_*.py`, fill the three
  `REPLACE-ME` values, `uv run pytest -s`. The download, gated publish, and
  render template.

## Not this skill

Building a new workbook from a spec belongs to the `tableau-build` skill in the
`dashboard-creation-tool` plugin, which generates XML rather than editing it. If
that plugin is not enabled, say so rather than building one here. Its XSD
validator and snippet files are listed as unverified inputs at the end of
[references/build-workflow.md](references/build-workflow.md).
