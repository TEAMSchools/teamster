# Comments and descriptions

No `paths:`, so this loads every session: one content test covers every code
comment, docstring, and `description:` in the repo, whatever the language.

- Keep the constraint and the why a future editor needs. Cut values another file
  owns and point to that file instead (`dlt/<source>/schedules.py`, an exposure,
  the model whose cron tick you share). Cut one-off measurements (GiB, row or
  rebuild counts, "measured on <date>") and history; those go in the commit and
  PR. A `Refs #N` pointer may stay in a comment, never in a description or
  docstring a caller reads.
- Editing inside a comment or description brings that whole block up to the
  test. Sweep the rest of the file only when asked.
- Where each kind of note goes. dbt: `.claude/rules/dbt-sql.md` and _YAML
  conventions_ in `.claude/rules/dbt-yaml.md`. Cube: a `description:` reaches
  callers through `/v1/meta`, so it says what the member means and where to go
  instead; build rationale (rollup row cost, refresh behavior, join choice) goes
  in a YAML comment. Python: docstring format is in `src/teamster/CLAUDE.md`.
