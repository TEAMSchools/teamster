# ps-plugins

Custom PowerSchool plugins built and maintained by the KTAF Data Team.

## About

This directory holds native PowerSchool plugins built to extend PS functionality
for KIPP Team & Family Schools. Each plugin lives in its own folder with its own
documentation and deployment guide.

KTAF runs PowerSchool in three regions, plus one shared test instance. Plugins
must be deployed and configured separately on each. **Miami is on Focus rather
than PowerSchool**, so it has no PS instance and no plugin here applies to it.

| Region   | PS Instance           |
| -------- | --------------------- |
| Newark   | psteam.kippnj.org     |
| Camden   | camden.kippnj.org     |
| Paterson | ps.kipppaterson.org   |
| Test     | kippnj2.clgpstest.com |

---

## Plugins

| Plugin          | Folder                                   | Status                                   | Description                                                   |
| --------------- | ---------------------------------------- | ---------------------------------------- | ------------------------------------------------------------- |
| Gradebook Audit | [`gradebook-audit/`](./gradebook-audit/) | Phase 1 complete, Phases 2–7 in progress | Manages gradebook assignment expectations and audit reporting |

---

## Reference Documentation

PowerSchool's developer documentation — plugin XML schema, database extensions,
PS-HTML page customization, PowerTeacher Pro — is a set of vendor PDFs in the
Data Team's shared Drive folder, not files in this repo. The
[index](./docs/reference/README.md) says what each document covers, when to
reach for it, and the Drive file ID to fetch it by.

---

## How to Deploy a Plugin

1. Navigate to the plugin folder
2. Read the plugin-specific `README.md` for setup requirements
3. Get the plugin zip — **don't build it by hand.** Either:
   - **Download it from CI:** open the latest
     [Build plugin](https://github.com/TEAMSchools/teamster/actions/workflows/build-plugin.yaml)
     run and download the `plugin-zips` artifact, or
   - **Build it locally**, from the repo root:
     `uv run --no-project python ps-plugins/scripts/build_plugin.py`, which
     writes to `ps-plugins/dist/`
4. Upload to PS via System Management → Server → Plugin Configuration

> ⚠️ Hand-zipping is how a required folder level once went missing, producing a
> plugin that installed cleanly and then silently didn't work. The build script
> validates that every path referenced in the plugin's XML resolves to a real
> file, and fails if it doesn't.

> ⚠️ Each PS instance requires its own deployment. Always check the instance
> deployment tracker in the plugin README before deploying.

---

## Contributing

- Create a branch for your changes
- Open a PR for review before merging to `main`
- Update the plugin version in `plugin.xml` and the deployment tracker in the
  plugin README after deploying

---

Maintained by the KTAF Data Team · data@kippnj.org
