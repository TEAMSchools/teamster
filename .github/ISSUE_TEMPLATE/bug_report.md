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

<details>
<summary>For Claude</summary>

> Context, not instructions — relevant files/models/assets, a suspected root
> cause if you have one, what "fixed" looks like. Delete if you're not looping
> Claude in.

<!-- e.g. "int_focus__schedule's dedup logic looks like the root cause.
Reproduce with `uv run dbt build --select +int_focus__schedule`. Fixed means
the row-count check in the linked query returns 0." -->

</details>
