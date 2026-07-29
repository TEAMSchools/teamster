# CLAUDE.md — `teamster/libraries/knowbe4/`

**KnowBe4** (security awareness training) REST integration.
`build_knowbe4_asset()` is a simple non-partitioned factory; `KnowBe4Resource`
paginates automatically in `list()`. Asset key:
`[code_location, "knowbe4", *resource.split("/")]` — the endpoint path becomes
key segments.
