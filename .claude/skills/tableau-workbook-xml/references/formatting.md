# Formatting, encoding and text-level traps

Small details that silently corrupt a workbook or a diff. All claims are
**Verified** unless marked.

## The paragraph-break sentinel

**Verified.** Inside `<formatted-text>`, a line break is its own run containing
the literal character `Æ` (U+00C6, bytes `C3 86`) followed by `&#10;`:

```xml
<run>Æ&#10;</run>
```

There were 235 of these in a 1.9 MB workbook and none of them render. It is
Tableau's internal marker, not content. Reproduce it byte-exactly in any new
`formatted-text`; a plain `<run>&#10;</run>` was never observed in the corpus.
Variants carrying formatting exist and behave the same:

```xml
<run fontalignment='0'>Æ&#10;</run>
<run fontcolor='#555555' fontname='Tableau Regular' fontsize='14'>Æ&#10;</run>
```

**Tooltips are the exception.** They use plain `&#10;` inside the text runs and
no `Æ` sentinel. See [dynamic-text.md](dynamic-text.md).

## CRLF: the trap that looks like it is handled

**Verified.** Workbook files downloaded from Server use CRLF line endings:
27,729 of them in the file worked on here.

`Path.read_text(encoding="utf-8")` applies universal newline translation. The
string it returns contains no `\r` at all, so:

```python
# WRONG. This looks like CRLF handling and is not.
t = path.read_text(encoding="utf-8")
nl = "\r\n" if "\r\n" in t else "\n"   # can never be true
```

The sniff always picks `\n`, and writing the file converts every line ending to
LF. The whole-file diff then becomes useless.

```python
# RIGHT. Python 3.13 supports newline= on Path.read_text.
t = path.read_text(encoding="utf-8", newline="")
...
path.write_text(out, encoding="utf-8", newline="")
```

Assert the CRLF count afterwards: it should change by exactly the number of
lines inserted or removed, and the bare-LF count should be zero.

```python
crlf = out.count("\r\n")
assert out.count("\n") - crlf == 0, "bare LF introduced"
```

This bug survived in the repack helper long after every edit script was fixed,
because nobody re-read the helper. The `.twb` on disk was correct and the one
inside the `.twbx` was not. `docs/tableau-xml/scripts/repack.py` now asserts
both.

## Number formats

**Verified.** Formats live on the `<column>` definition as `default-format`, and
apply everywhere the field is used (labels, tooltips, headers) with no per-sheet
work.

```xml
<column caption='% Failing' datatype='real' default-format='p0.0%'
        name='[Calculation_4005670422456098835]' role='measure' type='quantitative'>
```

Observed families:

| Value                        | Renders             | Notes                          |
| ---------------------------- | ------------------- | ------------------------------ |
| `p0%`                        | `69%`               | percentage, no decimals        |
| `p0.0%`                      | `49.4%`             | percentage, one decimal        |
| `n#,##0"%";-#,##0"%"`        | `85%`               | number family, literal percent |
| `n0;-0`                      | `209`               |                                |
| `*+0.0"pp";-0.0"pp";0.0"pp"` | `+18.0pp`, `-6.7pp` | custom, three sections         |

The custom family takes `positive;negative;zero`. The leading `*` is the
serialization marker; in Desktop's Custom box you type only the pattern. A
negative section with no minus sign renders the magnitude, which is what you
want when a glyph carries the direction:

```text
▲0.0"pp";▼0.0"pp";0.0"pp"
```

### Table calculations are the gap

**Not solved.** A percent-of-total value on a shelf (`pcto:usr:...:qk:2`) is not
a `<column>`, so `default-format` cannot reach it. No worksheet-level
`attr='number-format'` element existed anywhere in the corpus to copy, so the
element shape for formatting a table calc is unknown. The change was handed back
to be done in Desktop, which is three clicks. If you need this, capture a
Desktop-authored example first.

## Entity encoding inside attributes

**Verified.** Formulas and captions live in single-quoted attributes, so the
file is full of entity-encoded operators. When composing a formula in a script,
encode it the same way:

```text
&gt;   >        &lt;   <        &quot;   "        &apos;   '
&#10;  newline
```

A formula written with a raw `>` produces malformed XML; one written with a raw
`&` breaks the attribute.

### `<customized-label>` field references need the placeholder delimiters

**Verified.** A field reference inside a `customized-label` template requires
the `<` and `>` delimiters around the token, and in that context they are
encoded. Omitting them prints the field name literally rather than its value.

## Blanket string replacement is the recurring self-inflicted wound

**Verified twice, both costly.**

- A blanket `value='true'` to `value='false'` rewrote a parameter's domain
  `<member value='true'/>`, leaving `false` as the only legal value. The
  parameter action fired, the assignment was rejected, and nothing happened. The
  symptom looked like a broken action, not a broken domain.
- A regex manifest rebuild dropped a dotted entry, as described in
  [content-models.md](content-models.md).

Rule: every substitution is anchored and asserts it matched exactly once. Abort
loudly otherwise.

```python
new, n = re.subn(pattern, replacement, segment)
if n != 1:
    sys.exit(f"FAIL: {label} matched {n} times, expected 1")
```

## Two regex traps specific to this XML

**Greedy derivation prefixes.** A column-instance is
`[<prefixes>:<column>:<suffix>]`. Matching with a leading `(?:[a-z]+:)*` is
greedy and swallows an all-lowercase column name: on `[none:school:nk]` it
consumes `none:school:` and captures `nk` as the column. Parse from the right:
split on `:`, and if the last part is `nk`/`ok`/`qk`, the column is the
second-to-last.

**`<zone\b` matches `<zone-style>`.** The hyphen is a word boundary, so a
depth-counting scan over `<zone\b[^>]*>|</zone>` treats every `<zone-style>` as
an opening zone, inflates the depth and never closes. Use `<zone(?=[\s>])`.

## Variable shadowing truncated a workbook

**Verified.** A loop written as `for n, m in enumerate(kids)` clobbered the
outer regex match object `m` that held the dashboard span. The script wrote a
workbook truncated from 1.45M characters to 143k. Cheap guard, worth having in
every edit script:

```python
if abs(len(out) - len(src)) > 0.2 * len(src):
    sys.exit(f"FAIL: length moved {len(src)} -> {len(out)}")
```
