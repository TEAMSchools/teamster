---
paths:
  - "**/src/dbt/**/models/**"
  - "**/src/dbt/**/tests/**"
  - "**/src/cube/model/**"
  - "**/src/cube/*.js"
---

# Comments and descriptions

Loads on the first read of a dbt model or test, or a Cube model file. One
content test covers SQL comments, YAML comments, JS comments, and `description:`
alike.

- Keep the constraint and the why a future editor needs. Cut values another file
  owns and point to that file instead (`dlt/<source>/schedules.py`, an exposure,
  the model whose cron tick you share). Cut one-off measurements (GiB, row or
  rebuild counts, "measured on <date>") and history; those go in the commit and
  PR. A `Refs #N` pointer may stay in a comment, never a description.
- Editing inside a comment or description brings that whole block up to the
  test. Sweep the rest of the file only when asked.
- Where each kind of note goes. dbt: `.claude/rules/dbt-sql.md` and _YAML
  conventions_ in `.claude/rules/dbt-yaml.md`. Cube: a `description:` reaches
  callers through `/v1/meta`, so it says what the member means and where to go
  instead; build rationale (rollup row cost, refresh behavior, join choice) goes
  in a YAML comment.
