# Dynamic text: which surfaces resolve placeholders

Tableau embeds live values in text with a placeholder token in angle brackets.
Whether a token resolves depends on **which surface it is on**. Evidence from
one surface does not transfer to another. This cost more time than anything else
in the source project.

Marks: **Verified** = observed in a render. **Inferred** = present in a working
file but never rendered, which this project twice proved insufficient.

## Token forms

```text
<[federated.0n798br073i5kb170j6l90uiv50a].[usr:Calculation_4645249709926099321:qk]>
<[Parameters].[Parameter 11]>
<Data Update Time>
```

A field token names the datasource and the **column-instance as it appears in
that worksheet**, not the bare column name. The instance carries a derivation
prefix and a type suffix: `none:`/`usr:`/`avg:`/`attr:`/`pcto:usr:` and `:nk`
(nominal), `:ok` (ordinal), `:qk` (quantitative).

The field must be in the view. The source project put tooltip fields on the
Tooltip shelf after a `<lod>` on Detail doubled a percent-of-total axis to 200%
(see [layout-and-zones.md](layout-and-zones.md)); that Tooltip is safe is
Inferred, and [unverified-warnings.md](unverified-warnings.md) has the probe.

## The matrix

| Surface                                | Field token | Parameter token   | Notes                                      |
| -------------------------------------- | ----------- | ----------------- | ------------------------------------------ |
| Worksheet `<title>`                    | untested    | **works**         | Needs `show-title='true'` on the zone      |
| Worksheet `<caption>`                  | works       | untested          | Built-in `<Data Update Time>` verified     |
| Mark label `<customized-label>`        | **works**   | **renders blank** | Space is reserved, no text appears         |
| Tooltip `<customized-tooltip>`         | works       | works             | Two encodings exist; see below, unresolved |
| Dashboard text zone (`type-v2='text'`) | **never**   | **never**         | Dead text, no resolution at all            |
| Axis title (`<format attr='title'>`)   | untested    | untested          | Only static values observed in this corpus |

Bold entries were verified by rendering. Non-bold entries are inferred from
presence in a working file.

## Verified: parameter in a worksheet title

Probed deliberately: one sheet, one title, published to a scratch project, then
rendered twice through the render API with the parameter set each way. Rendered
`PROBE Projected EOY` and `PROBE On the books today`.

```xml
<worksheet name='GPA - Goal by grade'>
  <layout-options>
    <title>
      <formatted-text>
        <run fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'><![CDATA[<[Parameters].[Parameter 11]>]]></run>
      </formatted-text>
    </title>
  </layout-options>
  <table>
```

`<layout-options>` must precede `<table>`; see
[content-models.md](content-models.md).

### A title is invisible unless the zone shows it

**Verified, and it wasted a probe cycle.** Every body zone on the dashboard
carried `show-title='false'`. The first probe added a perfectly good title and
rendered nothing: no error, no partial text. The initial reading was "the
parameter syntax does not work," which was wrong.

```xml
<zone h='15668' id='151' name='GPA - Goal by grade' show-title='true' ... >
```

Flip the zone attribute in the dashboard's `<zones>` block, not the
`<devicelayouts>` copy. Any assertion that checks for a worksheet title must
also check the zone attribute, or it passes an invisible title.

## Verified: parameter in a mark label renders blank

Two mechanisms were tried in `<customized-label>`. Both failed on screen while
passing every structural check.

**Attempt 1: the parameter token directly.** The label reserved a blank line
between the caption and the number. No text, no error.

```xml
<run fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'><![CDATA[<[Parameters].[Parameter 11]>]]></run>
```

**Attempt 2: route the parameter through a calculated field on the Text shelf.**
Worse: the entire mark label disappeared. Caption, basis line and the 30pt
number all vanished (Verified). Neighbouring sheets rendered normally, so it was
specific to the two edited sheets. The reading that Text displaces
`customized-label` rather than supplementing it is the inference, not the
observation.

**What shipped instead:** static text in the same run style. The live value is
available on the worksheet-title surface, which does work, so put it there when
the layout allows.

## Verified: field tokens in a mark label work

This is how every big number on the dashboard renders.

```xml
<customized-label>
  <formatted-text>
    <run fontname='Tableau Regular' fontsize='13'>Students below 3.0</run>
    <run>Æ&#10;</run>
    <run fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'>Always projected</run>
    <run>Æ&#10;</run>
    <run fontcolor='#001e62' fontname='Tableau Semibold' fontsize='30'><![CDATA[<[federated.0n798br073i5kb170j6l90uiv50a].[usr:Calculation_6742351851630427295:qk]>]]></run>
  </formatted-text>
</customized-label>
```

`<run>Æ&#10;</run>` is the paragraph break; see [formatting.md](formatting.md).

## UNRESOLVED: the two tooltip encodings

This is the one genuinely open question. Settle it with a probe that renders, or
with a human hover; until one of those has happened, report any tooltip you
touched as unverified.

**Form A: one CDATA run holding the whole line.**

```xml
<run bold='true' fontsize='11'><![CDATA[<[fed].[none:school:nk]> — <[fed].[none:region:nk]>]]></run>
<run>Æ&#10;</run>
<run fontsize='10'><![CDATA[<[Parameters].[Parameter 1]> students: <[fed].[usr:Calculation_7200000000000000003:nk]>]]></run>
```

Present on `Y1 Landing - % ≥3.0 School Bars`, whose tooltips the workbook owner
described as excellent. That is second-hand, not a probe: whether this form
renders is unconfirmed by this project. It includes a **parameter** token, and
every reference in it carries an `:nk` suffix.

**Form B: the field instance alone in a bare run, delimiters split across run
boundaries.**

```xml
<run>&lt;</run>
<run>[fed].[none:teacher_name:nk]</run>
<run>&gt; — &lt;</run>
<run>[fed].[attr:Calculation_4005670422456631319:nk]</run>
<run>&gt;&#10;&lt;</run>
<run>[fed].[pcto:usr:Calculation_4005670422462021663:qk:2]</run>
<run><![CDATA[> graded course enrolments
A / B / C:  <]]></run>
```

Present on `Y1 Schools - Teacher Grade Distro`. Tableau wrote this itself; it
carries `:qk` suffixes and `pcto:` derivations. Line breaks are `&#10;` inside
the text runs: the tooltips in this corpus did not use the `Æ` sentinel.

**The contradiction.** A hand-built tooltip in form A, structurally
indistinguishable from the example above, rendered its instance strings
literally on the dashboard. The rebuild used form B and was published, but the
hover was never confirmed because a Desktop content-model error intervened
first.

Candidate explanations, none tested:

- The `:nk` versus `:qk` suffix matters for form A specifically.
- Form A works only for fields whose calc returns a pre-formatted string.
- The instance string was not registered as a `<column-instance>` in that
  worksheet's `<datasource-dependencies>`, or `[Parameters]` was not a
  dependency of the view. Added in review; the free grep probe is in
  [unverified-warnings.md](unverified-warnings.md). The source project checked
  element order, nesting path and datasource id, which is not the same check.
- Something else about the hand-built file differed.

**What to do until it is settled:** copy a known-working tooltip's runs verbatim
from the target workbook, keep run attributes and separator text, and substitute
only the `[datasource].[instance]` strings. Do not compose a tooltip from a
remembered template or from a snippet file; the plugin snippet described in
[build-workflow.md](build-workflow.md) uses `Æ&#9;` runs that this corpus never
showed in a tooltip. A tooltip is a hover, so a render cannot confirm it; ask a
human to hover and report.

## How to probe a new surface

The pattern that works, and is cheap:

1. Edit one sheet only, with a literal marker in the text (`PROBE `).
2. Repack and publish to the non-production project the user named.
3. Render through the API, setting the parameter explicitly if relevant.
4. Read the image. Confirm the marker _and_ the resolved value.
5. If the surface is a hover or a click, a render cannot prove it. Say so and
   ask a human.
6. If the element shape itself is unknown, ask the owner to author it in Desktop
   on a scratch copy and send the saved `.twb`; diff it against the base.
