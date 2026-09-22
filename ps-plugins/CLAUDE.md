# ps-plugins — project context

Custom PowerSchool (PS) plugins built by the KTAF Data Team. The in-progress
plugin is the **Gradebook Audit Plugin** (`gradebook-audit/`), which replaces a
Tableau gradebook data-quality dashboard with a native, PS-only implementation.

This file covers what's true in every session. Authoritative phase status and
per-instance deployment state live in
[`gradebook-audit/README.md`](./gradebook-audit/README.md) — update it when
either changes.

## Who you're working with

Someone on the KTAF Data Team who is **not a developer by background**. You
write and troubleshoot the plugin code; they deploy it to PowerSchool, test in
the live UI, and report what happened.

- Don't assume they'll debug XML or JS themselves.
- When a change needs manual setup in the PS admin UI (e.g. creating a database
  extension table), walk through the steps explicitly.
- They're **newer to git**. Say what a git command will do in plain terms as you
  run it. If a session shows they're comfortable, stop over-explaining.
- **Avoid WordPress analogies** for PS concepts — they haven't landed. Use
  PS/Oracle-native framing.

## Working conventions

- **The repo is ground truth, not a zip file.** Edit files directly and let git
  track the diff. Don't zip/unzip working copies — that was an older claude.ai
  workflow and doesn't apply here.
- **Test before calling anything done.** There's a shared PS test server
  (`kippnj2.clgpstest.com`) with live data. A change isn't finished until it's
  verified there. Code review alone is not completion.
- **Skip proof-of-concept scaffolding.** Build toward the real deployable
  artifact from the start.
- Branch, then PR into `main` — no direct commits to `main`.
- Named queries are namespaced `com.kippnj.<plugin>.<query_name>`. Extension
  groups and tables are uppercase with a `U_` prefix.

## PS gotchas that will bite you

- **No server-level PS access.** PowerSchool is CLG-hosted; there is no way to
  run Oracle DDL directly. Any new independent table must be created by hand
  through the PS admin UI (System Management → Data → Database Extensions)
  **before** its plugin XML will work. The XML will not auto-create it and
  **fails silently** if you assume it did.
- **Three PowerSchool regions** — Newark, Camden, Paterson — plus one shared
  test instance. A change isn't "deployed" until it's deployed to each
  individually. **Miami is on Focus, not PowerSchool**, so it has no PS instance
  and is out of scope for every plugin here. (This is also why `kippmiami` in
  `teamster` has no PowerSchool config.)
- **Paths in `plugin.xml` and `permission_mappings.xml` must match the actual
  `WEB_ROOT` directory layout.** A path pointing at a folder that doesn't exist
  fails silently at deploy time: the nav link 404s and permissions bind to
  nothing.
- Bump the `version` attribute in `plugin.xml` on every change.
- **Never hand-zip a plugin.** Run `python3 scripts/build_plugin.py` (or
  download the `plugin-zips` artifact from the Build plugin workflow). It
  validates that every path referenced in the XML resolves to a real file in the
  package and fails the build if not — which is exactly the bug hand-zipping
  introduced once.
- **Never run `trunk fmt --force` over these pages.** `.trunk/trunk.yaml`
  ignores prettier on `ps-plugins/**/*.html` because PowerSchool PSHTML `~[...]`
  constructs don't survive a generic HTML formatter. A plain
  `trunk check --force` will still report them — that's just noise, safe to
  ignore. But `trunk fmt --force` doesn't report, it rewrites, and it will
  silently mangle the `~[...]` syntax in all five pages.

## Reference materials

- **[`docs/reference/`](./docs/reference/)** — PowerSchool developer
  documentation PDFs, with an [index](./docs/reference/README.md) saying what
  each covers. Consult before changing `plugin.xml` (doc 03), `U_` tables or
  named queries (docs 04–05), the HTML pages' PS-HTML patterns (doc 05), or
  anything PowerTeacher Pro / teacher-facing (doc 06). Doc 05 is from 2015 / PS
  9.x — still the best PS-HTML reference, but verify its specifics against doc
  04 or the test instance. The PS Data Dictionary is in Drive, file ID in the
  index.
- **[`gradebook-audit/docs/`](./gradebook-audit/docs/)** — deployment guide.

### Related data models

These named queries reimplement, natively in PS, transformations that already
exist as DBT staging/intermediate models in the data platform repo
([`TEAMSchools/teamster`](https://github.com/TEAMSchools/teamster)). Read the
existing model before writing new named query or schema logic rather than
re-deriving a transformation — but treat `teamster` as the source of truth and
read it there; don't copy SQL into this repo where it would go stale.
