# Update mode

Re-run only the checks a change to a documented family affects. If the family
has no reference doc, stop and run document mode instead.

## Find what moved

```bash
git -C <worktree> diff --stat origin/main...HEAD -- <family .sql and .yml paths>
```

Then read each changed hunk in full before classifying it.

## Change → re-run

| Change                        | Re-run                                                                                                                                 |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| New or renamed column         | `yaml-audit.md` for that column; the `reference-doc.md` sections that name it; `tests-and-issues.md` for any test it needs             |
| Join, filter, or grain change | The prod grain check in `tests-and-issues.md`; then `qa-mode.md` → Refactor parity if values may move                                  |
| New view, sheet tab, or model | `intake-and-inventory.md` → Propose the boundary; a new doc section from `reference-doc.md` → Outline; a new route in the family skill |
| SQL comment only              | `tests-and-issues.md` → SQL comments (the comment-only proof and the CI warning)                                                       |

A rename sweep includes `*.md`: `rg -n '<old name>' --glob '*.{sql,yml,md}'`.

## Subagent checks after every update

- Every edited doc section: the cold review in `reference-doc.md`, scoped to
  those sections.
- Every edited family-skill file: a walk test (`model-skill.md` → Walk test) on
  a task that uses the edit.

Ask before each dispatch; the user may skip a trivial edit.
