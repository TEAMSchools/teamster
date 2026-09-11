# Unverified warnings, with probes

Nothing in this file was observed in the source project. Each entry is what an
experienced Tableau developer expects, offered in review, and each comes with
the probe that would move it to Verified inside the skill's own loop. Treat
every line as a hypothesis. Do not cite this file as evidence; run the probe.

## Publish and hand-over

- **Putting embedded connection credentials back after a publish.** That a
  publish drops them is now Verified (#5230; see
  [build-workflow.md](build-workflow.md)). Which call restores them is not:
  #5230 names `update_connection` with `oauth = True`, but the installed
  library's `update_connection` request never emits `oauth`, and
  `publish(connections=[...])` reported success on a live-connection workbook
  while leaving `embed_password` false. Probe: on a scratch copy, try each call,
  then read the connection back through the REST API and trigger a refresh.
  Until then, say in the hand-over that credentials were not carried.
- **`show_tabs=True` may change a user-visible setting.** Probe: read
  `wb.show_tabs` off the downloaded item and publish with the same value, then
  compare the two scratch copies.
- **Extract refresh schedules and permissions may or may not survive an
  Overwrite.** Probe: list tasks and permissions for the scratch workbook before
  and after an Overwrite and print the LUID both times.
- **Overwrite may match on name within project.** Verified so far (#5230): an
  Overwrite of the same target kept its LUID and `content_url` across about a
  dozen publishes. Still open: whether a second session's same-named workbook
  would be matched and overwritten. The skill requires a date in the review
  name; probe by publishing twice with the same name from two sessions and
  checking whether one workbook or two exist.

## Dynamic text

- **A token may resolve only if its column-instance is registered in that
  worksheet's `<datasource-dependencies>`.** The expectation is that a
  `<column-instance>` for the exact instance string must exist under the view's
  dependency block for that datasource, and that `[Parameters]` must be a
  dependency of the view for a parameter token to resolve. This is a candidate
  explanation for both the literal form-A tooltip and the blank parameter in a
  mark label; the source project checked element order, nesting and datasource
  id, not instance registration. Probe, no publish needed: compare the `<view>`
  dependency blocks of the working sheets and the broken sheets for the tokens
  they carry. Confirming probe: add the missing dependency to one broken sheet,
  change nothing else, publish to scratch, render. If it resolves, the open
  question in [dynamic-text.md](dynamic-text.md) closes.
- **The pane content model may be truncated as quoted.** Desktop's error printed
  `reference-line`, `customized-tooltip` and `customized-label` with no
  occurrence indicator, yet the corpus has panes without a reference line that
  Desktop opens. Cardinality is not established. Probe: grep the untouched base
  for a `<pane>` with no `<reference-line>`; it is a counter-example to the
  model read literally.

## Layout and formatting

- **A dimension on Tooltip may change the mark grain the same way Detail did.**
  The source verified only that a `<lod>` on Detail doubled a percent-of-total
  axis. Probe: move the identical field from `<lod>` to the Tooltip encoding on
  the same sheet, publish to scratch, render, read the axis maximum.
- **The reference line that rendered at `2.0` may have resolved correctly.** A
  raw GPA goal plotted on a 0 to 1 percent axis lands at 200%. Probe: point
  `value-column` at a constant `0.5` calculated field; if the line lands at 50%,
  rewrite the catalog entry as "express the reference value in the axis's
  units".
- **Text may wrap when the strip has vertical room.** The clip observations came
  from a text zone at `fixed-size='40'`. Probe: raise that zone and its parent
  to 80px with the same over-long caption, publish, render.
- **The character budget depends on font.** `97 * w / 39676` was calibrated on
  one 8pt italic Arial caption. Probe: repeat with the workbook's title font.
- **All pixel figures assume `sizing-mode='fixed'` at 1366x900 rendered at
  `Resolution.High`.** Probe before reusing any number on a dashboard with
  `automatic` or `range` sizing.
- **A worksheet-level format override may beat `default-format`.** Probe: grep
  the base for `attr='text-format'` or `attr='number-format'` scoped to the
  field before changing its column, then render two sheets that use it.
- **`<devicelayouts>` may be what phone and tablet viewers see.** The source
  verified only that editing it did not change the default layout. Probe: grep
  the base for `<device-layout`; if present, ask the owner how the dashboard is
  viewed, and either mirror the edit or say it was untouched.
- **The dual axis that drew no marks may have lacked a second `<pane>`.** Probe:
  ask the owner for a Desktop-authored dual axis on a scratch copy and diff it
  against the hand-built one.
- **`####` may be a width or font-size constraint, not a line count.** Probe:
  same sheet, 30pt number to 24pt, render.
- **A `<repository-location>` on a copied worksheet may bind it to the wrong
  server content.** The worksheet model lists it as an alternative to
  `<layout-options>`, so such a sheet also cannot carry a title. Probe: grep the
  base for `<repository-location` at worksheet depth.
- **Renaming a `<datasource>` `name` may orphan the packaged extract.**
  `repack.py` copies donor extracts blindly. Probe: rename a caption only,
  repack, render; then rename `name` on a throwaway.
- **A manifest entry copied from a workbook saved by a different Desktop build
  may itself be rejected.** Probe: compare `version` and `source-build` on the
  two workbooks before borrowing entries.
- **A new image or shape reference publishes blank if the asset is not in the
  donor archive.** Probe: list the donor's entries before adding a
  `type-v2='bitmap'` zone.
- **A stale `fixed-size` may look right in a render and wrong in Desktop.** The
  source verified only that Desktop may re-solve the layout on open. The margin
  to subtract is the container's own baseline gap from the geometry table, not a
  constant. Probe: hand the owner one resized zone with and without the updated
  `fixed-size` and ask which opens correctly.

## Process

- **Let Desktop write it and diff.** For any element shape this corpus never
  observed (a table-calc number format, a dual axis, a second tooltip form), ask
  the owner to make the change in Desktop on a scratch copy, save, and send the
  `.twb`; diff it against the base. This is the one oracle that outranks every
  checker here. The skill cannot run Desktop; the owner can.
- **`check_geometry.py` may false-positive on floating objects**, which
  legitimately overlap tiled siblings. Running both checkers against the
  untouched base before any edit (loop step 1) is what separates a checker bug
  from a workbook bug.
- **Cross-workbook parameter collisions may merge rather than delete.** The
  observed symptom (references pointing at an id now owned by an unrelated
  parameter) fits a merge on name and datatype as well as a deletion. The
  mitigation is the same: diff both lists against both sources.
