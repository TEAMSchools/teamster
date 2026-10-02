# Cube data issue notice templates

Post text uses standard markdown, because `slack_send_message` converts it
(`**bold**`, `_italic_`, `[text](url)`). Replace every `<...>`. Delete a bullet
that does not apply; keep every heading line.

## Top post

```text
:rotating_light: **Data issue: <plain-language name of the data>**
**Status at posting:** :red_circle: Investigating

**What's affected**
• **Unavailable:** <data Claude cannot see at all>
• **Untrustworthy:** <data Claude can see but is wrong, and how: undercounted, rates too high or too low, wrong school>

**Who this touches**
<regions, schools, grades, subjects, years>

**Not affected**
<what is still fine, especially another place to get the same numbers>

**What to do for now**
• <the workaround: where to get the right number instead>
• <if you already shared numbers from this data, what to do with them>

**Next update:** in this thread when a fix is underway :thread:
_Tracking: [#<n>](https://github.com/TEAMSchools/teamster/issues/<n>)_
```

## Fix in progress

Thread reply, not sent to the channel. Add the `Expected:` line only when
someone gave a date.

```text
:large_yellow_circle: **Fix in progress.** <1 plain sentence on what is changing>. We'll post here once it's confirmed in Cube.
**Expected:** <date>
```

## Resolution

Thread reply with `reply_broadcast: true`. Use the partial form when some
announced items are still open.

Full:

```text
:large_green_circle: **Fixed:** <data name> is now complete and accurate in Cube, starting with your next chat.
**What changed:** <1 sentence, for example "High school scores are back, so high school proficiency rates will go up.">
**If you pulled numbers before <date>:** <re-run them, or how far off they were>
```

Partial:

```text
:large_green_circle: **Partly fixed:** <fixed items> are now accurate in Cube, starting with your next chat.
**Still open:** <items>. We'll post here when those are fixed too.
**If you pulled numbers before <date>:** <re-run them, or how far off they were>
```

## Worked example: #5692

Posted 2026-10-02 as
<https://kippnj.slack.com/archives/C0BPH5STTTQ/p1790975134928079>, before the
status line read "Status at posting."

```text
:rotating_light: **Data issue: High school state test scores**
**Status:** :red_circle: Investigating

**What's affected**
• **Untrustworthy:** NJ high school state test results (NJSLA ELA09 and ALG01, plus NJGPA). Cube is missing about two-thirds of high school scores. The students left out aren't a random group, so **proficiency rates are wrong, not just counts**. For example, KHS ELA09 shows 13% proficient in Cube but is really 22%.
• **Untrustworthy (smaller gap):** About 1 in 10 state scores are missing across most years in NJ and Florida.
• **Possibly unavailable:** Miami 2025-26 state scores may not appear at all. We're still checking this one.

**Who this touches**
High schools (NCA, NLH, KHS) most of all, plus grade 8 Algebra I. K-8 NJ results are close to complete.

**Not affected**
The STAT Tableau dashboard. It doesn't read from Cube.

**What to do for now**
• For high school state test results, use the STAT dashboard, not Claude.
• If you've shared HS proficiency rates from Claude, treat them as too low.

**Next update:** in this thread as soon as we have a fix timeline :thread:
_Tracking: [#5692](https://github.com/TEAMSchools/teamster/issues/5692)_
```

What the example does right:

- The issue's root cause (an INNER join in an intermediate model) appears
  nowhere. The post says what is wrong with the numbers.
- "Rates are wrong, not just counts" tells readers that a smaller sample is not
  the only problem.
- The workaround names a specific other tool.
- The unverified Florida 2026 finding is hedged.
- "K-8 rows lose 0 to 2 scores each" became "close to complete": the gate drops
  counts under 10.
