# Procedure: Explain why a specific filter, column, or threshold exists

Some logic in this lineage has no recoverable business rationale — it was
inherited from an earlier model version and even the original author couldn't
reconstruct the "why" on review. Don't guess at a plausible-sounding reason and
present it as fact.

1. Search the reference doc first. Filters/columns with a known-undocumented
   rationale are called out there explicitly (e.g. `section_quarter_count >= 2`
   in `int_extracts__course_schedule_by_term` — see that model's section). Check
   the inline SQL comment at the derivation site too; a documented gap is noted
   in both places.
2. If the reference doc is silent, check git history yourself before answering:
   `git log -S'<column or literal>' -- <path>` to find the introducing commit,
   then read its message and diff. Check the PR that introduced it
   (`mcp__github__search_pull_requests`) for comment discussion.
3. Report what you find precisely — a commit message describing _what_ the code
   does is not the same as a business _why_. If you only find the mechanical
   description, say so plainly rather than inferring a rationale from what the
   filter happens to exclude today.
4. If this produces a new finding (no rationale exists, and it wasn't already
   documented), add it to the reference doc — a short paragraph at the relevant
   model's section stating what's known, what's not, and the introducing commit
   — plus a one-line comment at the derivation site in the SQL pointing back to
   the doc. This keeps the gap from being re-investigated from scratch next
   time.
