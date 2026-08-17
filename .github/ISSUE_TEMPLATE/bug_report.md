---
name: Bug report
about: Something isn't working as expected
title: "fix: "
labels: bug
---

## What's happening

<!-- What you expected, and what actually happened -->

## Steps to reproduce

1.
2.
3.

## Where

- **Code location / dbt project:**
- **Environment:** prod / branch deployment / local
- **Run, PR, or dashboard link (if any):**

## For Claude

> Write this as a prompt to `@claude` — what it needs to investigate or fix this
> — not a form to fill out. Delete if you're not looping Claude in.

@claude: <!-- e.g. "Start with int_focus__schedule — the dedup logic there
looks like the root cause. Reproduce with
`uv run dbt build --select +int_focus__schedule`. This is fixed when the
row-count check in the linked query returns 0." -->
