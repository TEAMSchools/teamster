"""Structural checks that catch what Tableau Desktop rejects and Server does not.

Server is lenient: it published and rendered a workbook whose worksheets were
missing `simple-id` and which used elements this Desktop build does not declare.
Desktop refused to open the same file. check_seq.py and check_zone_order.py both
passed it, because they only look at child ORDER inside pane / view / zone.

Two checks here:

**Required children.** Desktop reports
`missing elements in content model '(((layout-options?)|(repository-location?)),table,simple-id)'`
for a worksheet with no `simple-id`. So every worksheet needs `table` then
`simple-id`, in that order.

**Feature manifest.** THE authoritative check, learned the hard way. Desktop
does not validate against one schema per `version` -- each workbook declares the
features it uses in `<document-format-change-manifest>`, and an element whose
feature is undeclared gets `no declaration found for element 'x'`. That is why
`<button>` works in the Academic Health workbook (it declares
`BasicButtonObject`) and is rejected in the fidelity one (it does not), while
`datagraph` / `edit-parameter-action` are legal in fidelity (`DatagraphCoreV1`,
`ParameterAction`) and rejected in Academic Health. Same version, same build,
different legal element sets. Adding an element means adding its manifest entry.

**Required view children.** A `<view>` missing `<aggregation>` gets
`missing elements in content model '(datasources?,...,slices?,aggregation)'`.
Hand-built worksheets omit it easily.

**Unknown elements (weak).** Comparative only: any tag absent from a reference
workbook. Superseded by the manifest check above -- a --ref diff tells you what
changed, not what is legal.

Usage: uv run python check_twb.py <twb> [--ref <known-good.twb>]
"""

import re
import sys
from pathlib import Path

TAG = re.compile(r"<([a-zA-Z][\w.-]*)[ >/]")
CDATA = re.compile(r"<!\[CDATA\[.*?\]\]>", re.S)


def tags(text: str) -> set[str]:
    return set(TAG.findall(CDATA.sub("", text)))


def check_worksheets(text: str, name: str) -> int:
    """Every worksheet needs table then simple-id."""
    problems = 0
    for m in re.finditer(r"<worksheet name='([^']*)'>", text):
        ws = m.group(1)
        end = text.index("</worksheet>", m.end())
        seg = text[m.end() : end]
        # direct children only: strip nested worksheet-less depth by tag order
        order = [
            t
            for t in re.findall(r"\n {6}<([a-z-]+)[ >/]", seg)
            if t in ("layout-options", "repository-location", "table", "simple-id")
        ]
        if "simple-id" not in order:
            print(f"  {name}: worksheet {ws!r} has no <simple-id>")
            problems += 1
        elif order[-1] != "simple-id":
            print(
                f"  {name}: worksheet {ws!r} children end {order[-1]!r}, want simple-id"
            )
            problems += 1
    return problems


FEATURE_FOR_ELEMENT = {
    "button": "BasicButtonObject",
    "button-visual-state": "BasicButtonObject",
    "button-caption-font-style": "BasicButtonObjectTextSupport",
    "toggle-action": "CollapsiblePane",  # show/hide, not the plain button
    "datagraph": "DatagraphCoreV1",
    "dashboard-zone-visibility-node": "DatagraphNodeDashboardZoneVisibilityV1",
    "single-value-field-node": "DatagraphNodeSingleValueFieldV1",
    "edit-parameter-action": "ParameterAction",
}


def manifest(text: str) -> set[str]:
    m = re.search(
        r"<document-format-change-manifest>(.*?)</document-format-change-manifest>",
        text,
        re.S,
    )
    return set(re.findall(r"<([A-Za-z0-9_]+) ?/>", m.group(1))) if m else set()


def check_features(text: str, name: str) -> int:
    """An element whose feature the workbook does not declare will not open."""
    declared, present, problems = manifest(text), tags(text), 0
    for element, feature in FEATURE_FOR_ELEMENT.items():
        if element in present and feature not in declared:
            print(f"  {name}: <{element}> used but '{feature}' is not in the manifest")
            problems += 1
    return problems


def check_views(text: str, name: str) -> int:
    """Every <view> needs <aggregation>; Desktop rejects the file without it."""
    problems = 0
    for m in re.finditer(r"<worksheet name='([^']*)'>", text):
        end = text.index("</worksheet>", m.end())
        seg = text[m.end() : end]
        view = seg[seg.index("<view>") : seg.index("</view>")]
        if "<aggregation" not in view:
            print(f"  {name}: worksheet {m.group(1)!r} <view> has no <aggregation>")
            problems += 1
    return problems


#: Direct children of <pane>, in the only order Desktop accepts. Quoted verbatim
#: from its own refusal: "element 'reference-line' is not allowed for content
#: model '(view,mark,mark-sizing?,encodings?,label-data*,dropline?,trendline?,
#: reference-line,customized-tooltip,customized-label,style)'".
PANE_ORDER = [
    "view",
    "mark",
    "mark-sizing",
    "encodings",
    "label-data",
    "dropline",
    "trendline",
    "reference-line",
    "customized-tooltip",
    "customized-label",
    "style",
]


def check_pane_order(text: str, name: str) -> int:
    """Pane children must follow the content model's order.

    Inserting <customized-tooltip> straight after </encodings> puts it AHEAD of
    a sheet's reference lines. The file still parses as XML and Server still
    renders it -- only Desktop refuses to open it, with error D2E8DA72.
    """
    problems = 0
    rank = {e: i for i, e in enumerate(PANE_ORDER)}
    for w in re.finditer(r"<worksheet name='([^']*)'>", text):
        end = text.index("</worksheet>", w.end())
        seg = text[w.end() : end]
        for pane in re.finditer(r"<pane\b[^>]*>(.*?)</pane>", seg, re.S):
            depth, kids = 0, []
            for m in re.finditer(r"<(/?)([a-z-]+)\b[^>]*?(/?)>", pane.group(1)):
                close, tag, selfclose = m.group(1), m.group(2), m.group(3)
                if depth == 0 and not close and tag in rank:
                    kids.append(tag)
                if not close and not selfclose:
                    depth += 1
                elif close:
                    depth -= 1
            seen = [rank[k] for k in kids]
            if seen != sorted(seen):
                print(
                    f"  {name}: worksheet {w.group(1)!r} pane children out of order: "
                    f"{kids} -- model order is {PANE_ORDER}"
                )
                problems += 1
    return problems


def check_manifest_drop(text: str, ref: str, name: str) -> int:
    """Never reconstruct the manifest -- only insert into it.

    Entry names can contain dots (`_.fcp.VConnDownstreamExtractsWithWarnings...`)
    and a regex rebuild dropped one, which un-declared the feature that makes the
    extract's `user-specific` attribute legal.
    """
    lost = sorted(manifest(ref) | _dotted(ref))
    lost = [e for e in lost if e not in (manifest(text) | _dotted(text))]
    for e in lost:
        print(f"  {name}: manifest entry <{e}> present in the reference but dropped")
    return len(lost)


def _dotted(text: str) -> set[str]:
    m = re.search(
        r"<document-format-change-manifest>(.*?)</document-format-change-manifest>",
        text,
        re.S,
    )
    return set(re.findall(r"<([A-Za-z0-9_.]+) ?/>", m.group(1))) if m else set()


def check_unknown(text: str, ref: str, name: str) -> int:
    unknown = sorted(tags(text) - tags(ref))
    for t in unknown:
        print(f"  {name}: element <{t}> is absent from the reference workbook")
    return len(unknown)


if __name__ == "__main__":
    args = sys.argv[1:]
    ref_path = None
    if "--ref" in args:
        i = args.index("--ref")
        ref_path = Path(args[i + 1])
        args = args[:i] + args[i + 2 :]

    total = 0
    for a in args:
        p = Path(a)
        text = p.read_text(encoding="utf-8", newline="")
        n = check_worksheets(text, p.name)
        n += check_features(text, p.name)
        n += check_views(text, p.name)
        n += check_pane_order(text, p.name)
        if ref_path:
            ref_text = ref_path.read_text(encoding="utf-8", newline="")
            n += check_manifest_drop(text, ref_text, p.name)
            n += check_unknown(text, ref_text, p.name)
        print(f"{p.name}: {'CLEAN' if not n else f'{n} problem(s)'}")
        total += n
    sys.exit(1 if total else 0)
