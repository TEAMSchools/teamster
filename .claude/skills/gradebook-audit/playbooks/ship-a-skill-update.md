# Procedure: Ship a change to the gradebook-expectations-upload skill

**Trigger phrases:** "the plugin screen changed and T&L needs to know", "we need
to update the gradebook expectations skill", "push out a new version of the
academics chat skill", "T&L says the skill doesn't match what they're seeing",
"how do we get this fix to Teaching & Learning"

> Write for a Teaching & Learning reader, not a data-team one. No dbt model
> names, no SQL, no BigQuery. Describe what changes on screen and what they
> should do differently. If a sentence only makes sense to someone who has read
> the plugin source, rewrite it.

That instruction governs everything below it, including what you write in a
release note, a Slack message, or an email — not just the skill's own files.
Teaching & Learning never reads `plugin.xml` or a dbt model; they read a screen
and a set of instructions about that screen.

## The sequence

1. **Change the skill source**, under
   [`ps-plugins/skills/gradebook-expectations-upload/`](../../../../ps-plugins/skills/gradebook-expectations-upload/).
   This is a self-contained end-user artifact — `SKILL.md`, `INSTALL.md`,
   `playbooks/`, `references/` — and it never references `teamster` files, dbt
   models, or the warehouse, because a skill installed in Claude Desktop or
   claude.ai cannot resolve a path outside its own folder. If your change
   followed from a plugin change (`maintain-the-plugin.md`), this is usually
   `references/powerschool-navigation.md` (the screen-by-screen walkthrough) or
   `references/csv-format.md` (the CSV header contract) — check both against
   what actually changed on screen.
2. **Bump `version` in `SKILL.md`'s frontmatter.** This is the only way anyone
   downstream can tell which build they're running, especially on the per-user
   install path below, which has no auto-update. If you forget, the zip still
   builds, but two people can report different symptoms while both insisting
   they're "on the latest version" and there is no way to settle it.
3. **Let CI build the zip.** Pushing to `main` (or opening a PR) under
   `ps-plugins/**` runs `.github/workflows/build-plugin.yaml`, which packages
   the skill with `ps-plugins/scripts/build_skill.py`, fails the build if any
   relative markdown link inside the skill is broken, and uploads the result as
   a workflow artifact named `gradebook-expectations-upload`. There is no
   automated release publish — an administrator downloads the zip from that
   workflow run.
4. **Download the zip from the workflow run**, named
   `gradebook_expectations_upload_v<version>.zip` inside the
   `gradebook-expectations-upload` artifact, and stop to decide which
   distribution path applies. Both exist because the primary one has
   preconditions that can be off on any given day.

   Workflow artifacts expire — 90 days by default — so if no `ps-plugins/**`
   change has landed on `main` for a few months, the run you are looking for has
   no artifact attached any more. Re-run the workflow from the Actions UI
   (`workflow_dispatch`) to rebuild it; nothing is lost, the zip is just no
   longer sitting there.

## Distribution path A — organization skills (primary)

An administrator uploads the zip at claude.ai, under **Organization settings →
Skills → Add**. Every user in the organization gets it automatically, and
approving a later version updates everyone at once — Teaching & Learning
installs nothing and cannot end up stuck on a stale build.

Two preconditions, both organization-level settings an admin controls, not
something a Teaching & Learning user can turn on themselves:

- the organization is on a **Team or Enterprise** plan;
- **code execution is enabled** in organization settings — the skill needs it to
  write the CSV files.

If either is off, this path is unavailable and you fall through to path B.

## Distribution path B — per-user install (fallback)

Send the zip directly to whoever needs it, and have each person install it
themselves in Claude Desktop, following the skill's own
[`INSTALL.md`](../../../../ps-plugins/skills/gradebook-expectations-upload/INSTALL.md)
— point them at that file rather than re-explaining the click path here.

This path has **no auto-update**. Each person is running exactly whatever zip
they installed, indefinitely, until someone sends them a new one and they repeat
the install. That is why step 2's version bump matters here specifically — when
someone reports the skill doing something you already fixed, the only way to
tell whether they're behind or you have a new bug is the version, and there are
two ways to get it from them: the filename of the zip they downloaded and
installed (`gradebook_expectations_upload_v<version>.zip`), or asking them to
ask Claude, in a conversation where the skill is active, to open its own
`SKILL.md` and read back the `version:` field.

Use this path whenever organization skills are unavailable: the plan tier or the
code-execution setting is off, the recipient is outside the organization, or a
fix is urgent enough for one region that it can't wait on an administrator's
availability.

## Either way

Tell people what changed, in the same plain language as the skill itself. "The
CSV upload page now asks for a reason before deleting a quarter's rows" is
useful; "the named query changed to include `whenmodified`" is not — nobody
receiving it can act on it. If the change came from a plugin update
(`maintain-the-plugin.md`), that plain-language translation is the whole point
of this playbook existing as a separate step instead of ending at "the plugin
shipped."
