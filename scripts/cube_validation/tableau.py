"""Prove a workbook formula once: Tableau copy, number formats, exports, proof.

Tableau is written to in one place only: a copy named `ZZ-VALIDATE <workbook>`
in the `TEMP-CB` project, published with Overwrite. Nothing is deleted. The
copy drops the compared measures' number formats so its CSV exports carry raw
values, and unhides the compared sheet so it publishes as a view; `prove` compares those exports with the probe's values at the
sheet's displayed decimals.

XML edits are anchored text surgery, not an ElementTree round trip, so the
copy keeps its bytes and CRLF line endings (see the `tableau-workbook-xml`
skill). The input is a workbook downloaded from the site's own server.
"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import os
import re
import tempfile

# trunk-ignore(bandit/B405): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import tableauserverclient as TSC

from .compare import cell_verdict
from .config import Comparison

TEMP_PROJECT = "TEMP-CB"
COPY_PREFIX = "ZZ-VALIDATE "
API_VERSION = "3.25"
ENV_VARS = (
    "TABLEAU_SERVER_ADDRESS",
    "TABLEAU_SITE_ID",
    "TABLEAU_TOKEN_NAME",
    "TABLEAU_PERSONAL_ACCESS_TOKEN",
)
REFRESH_JOB_TYPES = ("refresh_extracts", "increment_extracts")
JOB_LOOKBACK = timedelta(days=8)
MAX_JOB_LOOKUPS = 200

# `<column\b` would also match `<column-instance`; the hyphen is a word boundary.
_COLUMN_TAG = re.compile(r"<column(?=[\s/>])[^>]*>")
_WORKSHEET = re.compile(r"<worksheet(?=[\s>]).*?</worksheet>", re.DOTALL)
# A format element with its own line: the line break before it goes with it.
_FORMAT_LINE = re.compile(r"(?:\r?\n[ \t]*)?<format(?=[\s/>])[^>]*/>")
_STYLE_RULE = re.compile(
    r"(?P<lead>(?:\r?\n[ \t]*)?)(?P<rule><style-rule(?=[\s>])[^>]*(?<!/)>.*?</style-rule>)",
    re.DOTALL,
)
_ATTR = re.compile(r"""([\w:.-]+)=(?:'([^']*)'|"([^"]*)")""")
_DEFAULT_FORMAT = re.compile(r"""\s+default-format=(?:'[^']*'|"[^"]*")""")
_THOUSANDS = re.compile(r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?")
_INSTANCE_SUFFIXES = {"nk", "ok", "qk"}
_WINDOW_TAG = re.compile(r"<window(?=[\s/>])[^>]*>")
_HIDDEN = re.compile(r"""\s+hidden=(?:'true'|"true")""")


class RefreshMovedError(RuntimeError):
    """An extract refresh started while the exports were being taken, twice."""


# --- workbook XML ------------------------------------------------------------


def _attrs(tag: str) -> dict[str, str]:
    return {m[1]: html.unescape(m[2] or m[3] or "") for m in _ATTR.finditer(tag)}


def _bare(name: str) -> str:
    return name[1:-1] if name.startswith("[") and name.endswith("]") else name


def _field_column(field_ref: str) -> str:
    """Return the column name of a `[datasource].[instance]` reference.

    Parsed from the right, because a greedy derivation prefix swallows an
    all-lowercase column name: `pcto:usr:Calculation_1:qk:2` reads
    `Calculation_1`, `none:region:nk` reads `region`.
    """
    instance = field_ref.rsplit("].[", 1)[-1].lstrip("[").rstrip("]")
    parts = instance.split(":")
    for i in range(len(parts) - 1, 0, -1):
        if parts[i] in _INSTANCE_SUFFIXES:
            return parts[i - 1]
    return instance


def _target_columns(root: ET.Element, measures: list[str]) -> set[str]:
    """Resolve measure captions or column names to bare column names."""
    targets: set[str] = set()
    missing = []
    for measure in measures:
        found = {
            _bare(col.get("name") or "")
            for col in root.iter("column")
            if measure
            in (col.get("caption"), col.get("name"), _bare(col.get("name") or ""))
        }
        if not found:
            missing.append(measure)
        targets |= found
    if missing:
        raise ValueError(f"no column with caption or name {', '.join(missing)}")
    return targets


def _is_target_format(attrs: dict[str, str], targets: set[str]) -> bool:
    return (
        attrs.get("attr") == "text-format"
        and _field_column(attrs.get("field", "")) in targets
    )


def drop_number_formats(twb_xml: str, measures: list[str]) -> str:
    """Remove the number formats of some measures, so exports carry raw values.

    Drops `default-format` from every `<column>` defining a named measure (the
    datasource copy and each worksheet's dependency copy) and every
    `text-format` rule on that measure inside a worksheet, table or pane
    style. Other measures and non-number format rules are untouched. Line
    endings are kept: each dropped rule takes its own line with it.

    Args:
        twb_xml: The workbook XML.
        measures: Captions or column names (with or without brackets).

    Returns:
        The edited workbook XML.

    Raises:
        ValueError: A measure names no column, or the edit removed a different
            number of formats than the parsed workbook holds.
    """
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)
    targets = _target_columns(root, measures)

    want_defaults = sum(
        1
        for col in root.iter("column")
        if _bare(col.get("name") or "") in targets
        and col.get("default-format") is not None
    )
    want_rules = sum(
        1
        for ws in root.iter("worksheet")
        for fmt in ws.iter("format")
        if _is_target_format(dict(fmt.attrib), targets)
    )

    dropped_defaults = 0

    def column_tag(m: re.Match) -> str:
        nonlocal dropped_defaults
        tag = m.group(0)
        if _bare(_attrs(tag).get("name", "")) not in targets:
            return tag
        new, n = _DEFAULT_FORMAT.subn("", tag)
        dropped_defaults += n
        return new

    out = _COLUMN_TAG.sub(column_tag, twb_xml)

    dropped_rules = 0

    def format_line(m: re.Match) -> str:
        nonlocal dropped_rules
        if not _is_target_format(_attrs(m.group(0)), targets):
            return m.group(0)
        dropped_rules += 1
        return ""

    def style_rule(m: re.Match) -> str:
        new = _FORMAT_LINE.sub(format_line, m.group("rule"))
        inner = re.sub(r"\A<[^>]*>|</style-rule>\Z", "", new)
        # A rule this edit emptied goes, with its line: no reference shows an
        # empty <style-rule> in a working workbook.
        if new != m.group("rule") and not inner.strip():
            return ""
        return m.group("lead") + new

    out = _WORKSHEET.sub(lambda ws: _STYLE_RULE.sub(style_rule, ws.group(0)), out)

    if (dropped_defaults, dropped_rules) != (want_defaults, want_rules):
        raise ValueError(
            f"dropped {dropped_defaults} column formats and {dropped_rules} "
            f"text-format rules; the workbook holds {want_defaults} and {want_rules}"
        )
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    if _empty_rules(ET.fromstring(out)) > _empty_rules(root):
        raise ValueError("the edit left an empty style-rule")
    return out


def expose_sheet(twb_xml: str, sheet: str) -> str:
    """Unhide a worksheet's window, so the sheet publishes as a view.

    A worksheet shown only inside a dashboard carries `hidden='true'` on its
    `<window>`, and the server publishes no view for it, so it cannot be
    exported. Only that attribute of that window is removed.

    Raises:
        ValueError: More than 1 worksheet window has that name.
    """
    matched = 0

    def window(m: re.Match) -> str:
        nonlocal matched
        tag = m.group(0)
        attrs = _attrs(tag)
        if attrs.get("class") != "worksheet" or attrs.get("name") != sheet:
            return tag
        matched += 1
        return _HIDDEN.sub("", tag)

    out = _WINDOW_TAG.sub(window, twb_xml)
    if matched > 1:
        raise ValueError(f"{matched} worksheet windows named {sheet!r}, expected 1")
    return out


def _empty_rules(root: ET.Element) -> int:
    return sum(
        1
        for ws in root.iter("worksheet")
        for rule in ws.iter("style-rule")
        if len(rule) == 0
    )


def displayed_decimals(format_string: str) -> int:
    """Return the digits of the compared value a number format displays.

    A percent displays the value times 100, so its fraction digits count 2
    more: `p0.0%` shows 0.912 as 91.2%, 3 digits of the fraction. Only the
    first (positive) section counts. Quoted and backslash-escaped text is
    literal, so `n#,##0"%"` is a whole number, not a percent.

    Args:
        format_string: A Tableau `default-format` or `text-format` value, such
            as `p0.0%`, `n#,##0`, `0.00` or `*+0.0"pp";-0.0"pp"`.

    Returns:
        The number of decimals of the underlying value.

    Raises:
        ValueError: The format is empty.
    """
    if not format_string:
        raise ValueError("empty number format")

    family = format_string[0] if format_string[0] in "npcCe*" else ""
    body = format_string[len(family) :]
    # Literals: "quoted text" and backslash-escaped characters.
    body = re.sub(r'"[^"]*"|\\.', "", body).split(";", 1)[0]

    fraction = 0
    if "." in body:
        fraction = len(re.match(r"[0#?]*", body.split(".", 1)[1]).group(0))
    percent = family == "p" or "%" in body
    return fraction + (2 if percent else 0)


def formula_fingerprint(twb_xml: str, sheet: str) -> str:
    """Fingerprint the workbook logic one sheet's numbers depend on.

    Covers each calculation in the sheet's datasource dependencies (formula
    and table-calculation settings, as canonical XML) and each filter on the
    sheet. Number formats, layout and data are left out, so dropping formats
    for the copy or refreshing an extract keeps the fingerprint, and editing a
    formula or a filter changes it. Relies on Tableau listing every column a
    sheet needs, nested calculations included, in its dependencies.

    Args:
        twb_xml: The workbook XML.
        sheet: The worksheet name.

    Returns:
        A sha256 hex digest.

    Raises:
        ValueError: The workbook has no worksheet of that name.
    """
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)
    ws = next(
        (w for w in root.iter("worksheet") if w.get("name") == sheet),
        None,
    )
    if ws is None:
        raise ValueError(f"the workbook has no worksheet {sheet!r}")

    parts = []
    for deps in ws.iter("datasource-dependencies"):
        for col in deps.findall("column"):
            calc = col.find("calculation")
            if calc is not None:
                parts.append(
                    [
                        "calculation",
                        deps.get("datasource") or "",
                        col.get("name") or "",
                        ET.canonicalize(ET.tostring(calc, encoding="unicode")),
                    ]
                )
    for flt in ws.iter("filter"):
        parts.append(["filter", ET.canonicalize(ET.tostring(flt, encoding="unicode"))])

    return hashlib.sha256(json.dumps(sorted(parts)).encode("utf-8")).hexdigest()


_PARAMETERS_DS = re.compile(
    r"<datasource\b(?=[^>]*\bname='Parameters')[^>]*[^/]>.*?</datasource>", re.DOTALL
)
_COLUMN_BLOCK = re.compile(r"<column\b[^>]*?(?:/>|>.*?</column>)", re.DOTALL)


def set_parameters(twb_xml: str, values: dict[str, str]) -> str:
    """Set workbook parameters' current values, so the sheet exports them.

    The REST export cannot pass a parameter, so the proof copy carries it:
    each parameter's `value` and its calculation's formula become the chosen
    member's stored text. Only the matched column's 2 attributes change.

    Args:
        twb_xml: The workbook XML.
        values: Parameter caption (or name) to the member to show.

    Raises:
        ValueError: A caption names no parameter, the parameter has no member
            list, or the value is not one of its members.
    """
    block_match = _PARAMETERS_DS.search(twb_xml)
    if block_match is None:
        raise ValueError("the workbook has no parameters")
    block = block_match.group(0)
    for wanted_name, wanted in values.items():
        found = None
        names = []
        for column in _COLUMN_BLOCK.finditer(block):
            attrs = _attrs(column.group(0).split(">", 1)[0])
            names.append(attrs.get("caption") or _bare(attrs.get("name", "")))
            if wanted_name in (
                attrs.get("caption"),
                attrs.get("name"),
                _bare(attrs.get("name", "")),
            ):
                found = column
                break
        if found is None:
            raise ValueError(
                f"no parameter {wanted_name!r}; the workbook has {', '.join(names)}"
            )
        text = found.group(0)
        members = {
            _unquote(html.unescape(m[1])): m[1]
            for m in re.finditer(r"<member\b[^>]*?\bvalue='([^']*)'", text)
        }
        if not members:
            raise ValueError(
                f"parameter {wanted_name!r} has no member list to choose from"
            )
        if wanted not in members:
            raise ValueError(
                f"{wanted!r} is not a member of {wanted_name!r}: {', '.join(members)}"
            )
        raw = members[wanted]
        start, rest = text.split(">", 1)
        start = re.sub(
            r"\bvalue='[^']*'", lambda _, raw=raw: f"value='{raw}'", start, count=1
        )
        rest = re.sub(
            r"(<calculation\b[^>]*?\bformula=')[^']*(')",
            lambda m, raw=raw: f"{m[1]}{raw}{m[2]}",
            rest,
            count=1,
        )
        block = block.replace(text, f"{start}>{rest}", 1)
    return twb_xml[: block_match.start()] + block + twb_xml[block_match.end() :]


def _unquote(text: str) -> str:
    return text[1:-1] if len(text) > 1 and text[0] == text[-1] == '"' else text


# A shelf: `<rows onTop='true'>(A / (B / C))</rows>`, or empty as `<rows />`.
_SHELF_TAG = re.compile(
    r"<(?P<tag>rows|cols)(?P<attrs>(?:\s[^>]*?)?)\s*(?:/>|>(?P<body>[^<]*)</(?P=tag)>)"
)
_BRACKETED = r"\[(?:[^\]]|\]\])*\]"
_SHELF_TOKEN = re.compile(
    rf"\s*(?:(?P<ref>{_BRACKETED}(?:\.{_BRACKETED})?)"
    r"|(?P<op>[/+])|(?P<open>\()|(?P<close>\)))"
)
_DEPENDENCIES = re.compile(
    r"<datasource-dependencies\b[^>]*>.*?</datasource-dependencies>", re.DOTALL
)
_INSTANCE_SUFFIX = {"nominal": "nk", "ordinal": "ok", "quantitative": "qk"}
SHELF_NAMES = {"rows": "rows", "cols": "columns"}


@dataclass
class _Group:
    """A parenthesized shelf expression: fields nested (`/`) or side by side (`+`)."""

    items: list[_Group | str]
    ops: list[str]


def _parse_shelf(text: str) -> _Group | str | None:
    tokens = []
    end = 0
    for m in _SHELF_TOKEN.finditer(text):
        if m.start() != end:
            break
        tokens.append((m.lastgroup, m[m.lastgroup or ""]))
        end = m.end()
    if text[end:].strip():
        raise ValueError(f"cannot read the shelf {text!r}")
    if not tokens:
        return None
    at = 0

    def expect(kind: str) -> str:
        nonlocal at
        if at >= len(tokens) or tokens[at][0] != kind:
            raise ValueError(f"cannot read the shelf {text!r}")
        at += 1
        return tokens[at - 1][1]

    def operand() -> _Group | str:
        if at < len(tokens) and tokens[at][0] == "open":
            expect("open")
            node = expression()
            expect("close")
            return node
        return expect("ref")

    def expression() -> _Group | str:
        items, ops = [operand()], []
        while at < len(tokens) and tokens[at][0] == "op":
            ops.append(expect("op"))
            items.append(operand())
        return items[0] if len(items) == 1 else _Group(items, ops)

    node = expression()
    if at != len(tokens):
        raise ValueError(f"cannot read the shelf {text!r}")
    return node


def _shelf_text(node: _Group | str) -> str:
    if isinstance(node, str):
        return node
    out = _shelf_text(node.items[0])
    for op, item in zip(node.ops, node.items[1:], strict=True):
        out += f" {op} {_shelf_text(item)}"
    return f"({out})"


def _shelf_leaves(node: _Group | str | None) -> list[str]:
    if node is None:
        return []
    if isinstance(node, str):
        return [node]
    return [leaf for item in node.items for leaf in _shelf_leaves(item)]


def _without(
    node: _Group | str | None, drop: Callable[[str], bool]
) -> _Group | str | None:
    """The shelf with every field `drop` matches taken out."""
    if node is None or isinstance(node, str):
        return None if node is None or drop(node) else node
    items: list[_Group | str] = []
    ops: list[str] = []
    for i, item in enumerate(node.items):
        kept = _without(item, drop)
        if kept is None:
            continue
        if items:
            ops.append(node.ops[i - 1])
        items.append(kept)
    if not items:
        return None
    return items[0] if len(items) == 1 else _Group(items, ops)


def _nested_under(node: _Group | str | None, ref: str) -> _Group | str:
    """The shelf with `ref` nested innermost, as Tableau writes `(A / (B / C))`."""
    if node is None:
        return ref
    if isinstance(node, _Group) and set(node.ops) == {"/"}:
        return _Group([*node.items[:-1], _nested_under(node.items[-1], ref)], node.ops)
    return _Group([node, ref], ["/"])


def _xml_attr(value: str) -> str:
    for raw, escaped in (
        ("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("'", "&apos;"),
        ('"', "&quot;"), ("\n", "&#10;"), ("\r", "&#13;"),
    ):  # fmt: skip
        value = value.replace(raw, escaped)
    return value


def _xml_element(el: ET.Element, indent: str, nl: str) -> str:
    """Write an element the way Tableau does: single quotes, 2-space nesting."""
    if (el.text or "").strip() or any("{" in k for k in el.attrib):
        raise ValueError(f"cannot copy <{el.tag} name={el.get('name')!r}>")
    attrs = "".join(f" {k}='{_xml_attr(v)}'" for k, v in el.attrib.items())
    children = list(el)
    if not children:
        return f"{indent}<{el.tag}{attrs} />"
    inner = nl.join(_xml_element(c, indent + "  ", nl) for c in children)
    return f"{indent}<{el.tag}{attrs}>{nl}{inner}{nl}{indent}</{el.tag}>"


def _ref_column(ref: str) -> str:
    """The column name of a shelf field, as the XML escapes it or not."""
    return _field_column(html.unescape(ref))


def set_shelves(twb_xml: str, sheet: str, shelves: dict[str, Any]) -> str:
    """Reshape one worksheet's rows and columns, so it exports at a new grain.

    Each `drop` caption leaves the sheet's rows and columns; each `add` caption
    is nested innermost on its shelf as a dimension (`none`, the instance the
    workbook already uses for that field when there is one). An added field the
    sheet does not list joins its datasource dependencies, copied from the
    datasource. Tableau recomputes every measure at the new grain. A dropped
    field's sorts and formats go with it, and so does any table calculation
    along it (see `_strip_dropped`); its filters stay. Each `clear_filters`
    caption's filters are reset to keep every member. Only that worksheet's
    text changes.

    Args:
        twb_xml: The workbook XML.
        sheet: The worksheet name.
        shelves: `{drop: [caption], add: {rows: [caption], cols: [caption]},
            clear_filters: [caption]}`.

    Raises:
        ValueError: The workbook has no such worksheet, a dropped caption is
            not on the sheet's rows or columns, an added caption names no
            field of the sheet's datasources (or more than 1), names a
            measure, a calculation the sheet does not list, or a field
            already on the rows or columns, or a cleared caption names no
            filter of the sheet or a filter not on members.
    """
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)
    ws = next((w for w in root.iter("worksheet") if w.get("name") == sheet), None)
    blocks = [
        m
        for m in _WORKSHEET.finditer(twb_xml)
        if _attrs(m[0].split(">", 1)[0]).get("name") == sheet
    ]
    if ws is None or len(blocks) != 1:
        raise ValueError(f"the workbook has no worksheet {sheet!r}")
    block = blocks[0]
    text = block[0]
    nl = "\r\n" if "\r\n" in twb_xml else "\n"

    caption = {}
    for col in ws.iter("column"):
        name = _bare(col.get("name") or "")
        caption.setdefault(name, col.get("caption") or name)

    def shown(ref: str) -> str:
        column = _ref_column(ref)
        return caption.get(column, column.lstrip(":"))

    found_tags = list(_SHELF_TAG.finditer(text))
    tags = {m["tag"]: m for m in found_tags}
    if len(tags) != len(found_tags):
        raise ValueError(f"sheet {sheet!r} has more than 1 rows or cols shelf")
    trees = {
        tag: _parse_shelf(html.unescape(m["body"] or "")) for tag, m in tags.items()
    }
    on_shelves = [
        shown(leaf) for tree in trees.values() for leaf in _shelf_leaves(tree)
    ]

    def is_named(ref: str, wanted: str) -> bool:
        return wanted in (shown(ref), _ref_column(ref))

    before = {leaf for t in trees.values() for leaf in _shelf_leaves(t)}
    for wanted in shelves.get("drop", []):
        if not any(
            is_named(leaf, wanted) for t in trees.values() for leaf in _shelf_leaves(t)
        ):
            raise ValueError(
                f"{wanted!r} is not on the rows or columns of {sheet!r}; they "
                f"hold {', '.join(dict.fromkeys(on_shelves)) or 'nothing'}"
            )
        trees = {
            tag: _without(tree, lambda ref, w=wanted: is_named(ref, w))
            for tag, tree in trees.items()
        }
    kept = {leaf for t in trees.values() for leaf in _shelf_leaves(t)}
    dropped = {_ref_column(r) for r in before - kept} - {_ref_column(r) for r in kept}
    calcs = _table_calcs_along(ws, dropped)
    trees = {
        tag: _without(tree, lambda ref: ref in calcs) for tag, tree in trees.items()
    }

    top = root.find("datasources")
    datasources = {
        ds.get("name") or "": ds
        for ds in ([] if top is None else top.findall("datasource"))
    }
    dependencies = {
        deps.get("datasource") or "": deps
        for deps in ws.iter("datasource-dependencies")
    }
    inserts: dict[str, list[ET.Element]] = {}
    for tag, wanted_list in shelves.get("add", {}).items():
        if tag not in tags:
            raise ValueError(f"sheet {sheet!r} has no {SHELF_NAMES[tag]} shelf")
        for wanted in wanted_list:
            ds_name, col, listed = _added_column(
                wanted, sheet, dependencies, datasources
            )
            name = _bare(col.get("name") or "")
            if col.get("role") == "measure":
                raise ValueError(f"{wanted!r} is a measure; add a dimension")
            if col.find("calculation") is not None and not listed:
                raise ValueError(
                    f"{wanted!r} is a calculation {sheet!r} does not list; add a "
                    "plain field or one the sheet uses"
                )
            if any(
                _ref_column(leaf) == name
                for t in trees.values()
                for leaf in _shelf_leaves(t)
            ):
                raise ValueError(
                    f"{wanted!r} is already on the rows or columns of {sheet!r}"
                )
            instance = _dimension_instance(root, ws, ds_name, col)
            deps = dependencies[ds_name]
            if not listed:
                inserts.setdefault(ds_name, []).append(col)
            if not any(
                i.get("name") == instance.get("name")
                for i in deps.findall("column-instance")
            ):
                inserts.setdefault(ds_name, []).append(instance)
            ref = f"[{ds_name}].{instance.get('name')}"
            trees[tag] = _nested_under(trees[tag], ref)

    def with_inserts(m: re.Match) -> str:
        ds_name = _attrs(m[0].split(">", 1)[0]).get("datasource", "")
        added = inserts.pop(ds_name, [])
        if not added:
            return m[0]
        head, close = m[0].rsplit("</datasource-dependencies>", 1)
        indent = head[len(head.rstrip(" \t")) :]
        lines = [_xml_element(el, indent + "  ", nl).lstrip(" \t") for el in added]
        body = f"{nl}{indent}  ".join(lines)
        return f"{head}  {body}{nl}{indent}</datasource-dependencies>{close}"

    text = _DEPENDENCIES.sub(with_inserts, text)

    def shelf(m: re.Match) -> str:
        tree = trees[m["tag"]]
        if tree == _parse_shelf(html.unescape(m["body"] or "")):
            return m[0]
        attrs = m["attrs"].rstrip()
        if tree is None:
            return f"<{m['tag']}{attrs} />"
        body = _shelf_text(tree).replace("&", "&amp;").replace("<", "&lt;")
        return f"<{m['tag']}{attrs}>{body.replace('>', '&gt;')}</{m['tag']}>"

    text = _SHELF_TAG.sub(shelf, text)
    text = _strip_dropped(text, dropped, calcs)
    for wanted in shelves.get("clear_filters", []):
        text = _clear_filter(text, wanted, sheet, shown, is_named)
    out = twb_xml[: block.start()] + text + twb_xml[block.end() :]
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    ET.fromstring(out)
    return out


def _table_calcs_along(ws: ET.Element, dropped: set[str]) -> set[str]:
    """The sheet's table calculations that order or address along a dropped
    column, as `[datasource].[instance]` refs.
    """
    found = set()
    for deps in ws.iter("datasource-dependencies"):
        for instance in deps.findall("column-instance"):
            calc = instance.find("table-calc")
            if calc is None:
                continue
            fields = [v for el in calc.iter() for v in el.attrib.values() if "].[" in v]
            if any(_field_column(v) in dropped for v in fields):
                found.add(f"[{deps.get('datasource')}].{instance.get('name')}")
    return found


def _element(tag: str) -> re.Pattern:
    """One `tag` element, empty or with a body, with the line it starts."""
    return re.compile(
        rf"(?:\r?\n[ \t]*)?<{tag}(?=[\s/>])[^>]*?(?:/>|>.*?</{tag}>)", re.DOTALL
    )


_EMPTY_ELEMENT = re.compile(r"(?:\r?\n[ \t]*)?<[\w:-]+(?=[\s/])[^>]*/>")
_SLICE = re.compile(r"(?:\r?\n[ \t]*)?<column>([^<]*)</column>")
_EMPTY_STYLE_RULE = re.compile(
    r"(?:\r?\n[ \t]*)?<style-rule(?=[\s>])[^>]*>\s*</style-rule>"
)
# What sorts or formats one field, and goes when the field leaves the view.
_PER_FIELD = {"natural-sort", "sort", "format"}


def _strip_dropped(text: str, dropped: set[str], calcs: set[str]) -> str:
    """A reshaped worksheet without what still leans on a dropped field.

    A sort or format on a dropped column goes. A table calculation along one
    goes entirely (its instance, every encoding, format, label run, filter and
    slice naming it), since along the remaining fields it would mean something
    else. Filters on a dropped column stay: they keep filtering, and the
    filter cards on the sheet and its dashboards name them.
    """

    def on_dropped(attrs: dict[str, str]) -> bool:
        ref = attrs.get("field") or attrs.get("column") or ""
        return "].[" in ref and _field_column(ref) in dropped

    def names_calc(attrs: dict[str, str]) -> bool:
        return bool({attrs.get("field"), attrs.get("column")} & calcs)

    def head(element: str) -> tuple[str, dict[str, str]]:
        tag = element.lstrip().split(">", 1)[0]
        return tag[1:].split(None, 1)[0].rstrip("/"), _attrs(tag)

    def empty(m: re.Match) -> str:
        tag, attrs = head(m[0])
        if names_calc(attrs) or (tag in _PER_FIELD and on_dropped(attrs)):
            return ""
        return m[0]

    def dependencies(m: re.Match) -> str:
        ds = _attrs(m[0].split(">", 1)[0]).get("datasource", "")
        return _element("column-instance").sub(
            lambda c: (
                ""
                if f"[{ds}].{_attrs(c[0].lstrip().split('>', 1)[0]).get('name')}"
                in calcs
                else c[0]
            ),
            m[0],
        )

    def body(m: re.Match) -> str:
        tag, attrs = head(m[0])
        if names_calc(attrs) or (tag == "format" and on_dropped(attrs)):
            return ""
        return m[0]

    def run(m: re.Match) -> str:
        content = html.unescape(m[0])
        return "" if any(ref in content for ref in calcs) else m[0]

    out = _DEPENDENCIES.sub(dependencies, text)
    out = _EMPTY_ELEMENT.sub(empty, out)
    for tag in ("format", "filter"):
        out = _element(tag).sub(body, out)
    out = _element("run").sub(run, out)
    out = _SLICE.sub(lambda m: "" if html.unescape(m[1]) in calcs else m[0], out)
    # A rule this edit emptied goes: no reference shows an empty <style-rule>.
    if not _EMPTY_STYLE_RULE.search(text):
        out = _EMPTY_STYLE_RULE.sub("", out)
    return out


def _clear_filter(
    text: str,
    wanted: str,
    sheet: str,
    shown: Callable[[str], str],
    is_named: Callable[[str, str], bool],
) -> str:
    """A worksheet whose filters on `wanted` keep every member.

    Each such filter keeps its element and attributes (a context filter stays
    one, and its filter cards still name it); its members become the level's
    every member, the form an untouched All filter takes.
    """
    nl = "\r\n" if "\r\n" in text else "\n"
    found = 0

    def clear(m: re.Match) -> str:
        nonlocal found
        element = m[0].lstrip()
        lead = m[0][: len(m[0]) - len(element)]
        opening = element.split(">", 1)[0]
        column = _attrs(opening).get("column", "")
        if not is_named(column, wanted):
            return m[0]
        found += 1
        if _attrs(opening).get("class") != "categorical":
            raise ValueError(
                f"the filter on {wanted!r} on {sheet!r} is not on members; "
                "only a member filter can be cleared"
            )
        indent = lead.lstrip("\r\n")
        level = _xml_attr("[" + column.rsplit("].[", 1)[-1])
        members = (
            f"<groupfilter function='level-members' level='{level}' "
            "user:ui-enumeration='all' user:ui-marker='enumerate' />"
        )
        opening = opening.rstrip("/").rstrip()
        return f"{lead}{opening}>{nl}{indent}  {members}{nl}{indent}</filter>"

    out = _element("filter").sub(clear, text)
    if not found:
        on_sheet = [
            shown(_attrs(m[0].lstrip().split(">", 1)[0]).get("column", ""))
            for m in _element("filter").finditer(text)
        ]
        raise ValueError(
            f"{sheet!r} has no filter on {wanted!r}; it filters "
            f"{', '.join(dict.fromkeys(on_sheet)) or 'nothing'}"
        )
    return out


def _named(columns: list[ET.Element], wanted: str) -> list[ET.Element]:
    return [
        c for c in columns if wanted in (c.get("caption"), _bare(c.get("name") or ""))
    ]


def _added_column(
    wanted: str,
    sheet: str,
    dependencies: dict[str, ET.Element],
    datasources: dict[str, ET.Element],
) -> tuple[str, ET.Element, bool]:
    """Find a field to add: its datasource, its column, and whether the sheet
    lists it. Only a datasource's own columns count, never its extract's.
    """
    found = []
    for ds_name, deps in dependencies.items():
        listed = _named(deps.findall("column"), wanted)
        source = datasources.get(ds_name)
        defined = [] if source is None else _named(source.findall("column"), wanted)
        if listed or defined:
            found.append((ds_name, (listed or defined)[0], bool(listed)))
    if not found:
        raise ValueError(
            f"the workbook has no field {wanted!r} on the datasources of {sheet!r}"
        )
    if len(found) > 1:
        raise ValueError(
            f"{wanted!r} names a field on {len(found)} datasources of {sheet!r}"
        )
    return found[0]


def _dimension_instance(
    root: ET.Element, ws: ET.Element, ds_name: str, col: ET.Element
) -> ET.Element:
    """The `none` instance of a field: the sheet's own, the workbook's, or new."""
    name = col.get("name") or ""
    for scope in (ws, root):
        for deps in scope.iter("datasource-dependencies"):
            if deps.get("datasource") != ds_name:
                continue
            for instance in deps.findall("column-instance"):
                if (
                    instance.get("column") == name
                    and instance.get("derivation") == "None"
                ):
                    return instance
    kind = col.get("type") or "nominal"
    return ET.Element(
        "column-instance",
        {
            "column": name,
            "derivation": "None",
            "name": f"[none:{_bare(name)}:{_INSTANCE_SUFFIX.get(kind, 'nk')}]",
            "pivot": "key",
            "type": kind,
        },
    )


def _parameter_names(twb_xml: str) -> set[str]:
    # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
    root = ET.fromstring(twb_xml)
    names: set[str] = set()
    for ds in root.iter("datasource"):
        if ds.get("name") != "Parameters":
            continue
        for col in ds.findall("column"):
            names |= {
                n
                for n in (
                    col.get("caption"),
                    col.get("name"),
                    _bare(col.get("name") or ""),
                )
                if n
            }
    return names


def split_cuts(
    cuts: list[dict[str, Any]], twb_xml: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split cuts into those a REST export can take and those it cannot.

    A cut that sets a workbook parameter is proven in the browser: the server
    rejects parameter values on export here.

    Args:
        cuts: The comparison's cuts, each `{caption: value}`.
        twb_xml: The workbook XML, read for its parameter captions.

    Returns:
        `(exportable, browser)`, each in the order given.
    """
    params = _parameter_names(twb_xml)
    exportable, browser = [], []
    for cut in cuts:
        (browser if params & set(cut) else exportable).append(cut)
    return exportable, browser


# --- the proof ---------------------------------------------------------------


@dataclass(frozen=True)
class Proof:
    """The outcome of proving one comparison's probe against the sheet.

    Attributes:
        fingerprint: `formula_fingerprint` of the sheet the proof covers.
        cells: Cells present on both sides and compared.
        failures: One line per cell that differs or is on one side only.
        proven_at: When the comparison ran.
        browser: Cuts that set a parameter, to prove in the browser.
    """

    fingerprint: str
    cells: int
    failures: list[str]
    proven_at: datetime
    browser: list[dict[str, Any]] = field(default_factory=list)

    @property
    def proven(self) -> bool:
        """True when at least 1 cell was compared and none failed."""
        return self.cells > 0 and not self.failures


def _key_text(value: Any) -> str:
    """Key text that treats 2026, 2026.0 and '2026' alike."""
    if value is None:
        return ""
    text = str(value).strip()
    if _THOUSANDS.fullmatch(text):
        text = text.replace(",", "")
    try:
        number = Decimal(text)
    except InvalidOperation:
        return text
    return format(number.normalize(), "f") if number.is_finite() else text


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, (int, float)):
        return None if value is None else float(value)
    text = str(value).strip()
    if not text:
        return None
    if "%" in text or any(c.isalpha() and c not in "eE" for c in text):
        raise ValueError(
            f"export value {text!r} still carries a number format; "
            "publish the copy through drop_number_formats"
        )
    if _THOUSANDS.fullmatch(text):
        text = text.replace(",", "")
    return float(text)


def _index(
    rows: list[dict[str, Any]], dims: list[str], side: str, failures: list[str]
) -> tuple[dict[tuple, float | None], dict[tuple, str]]:
    values: dict[tuple, float | None] = {}
    labels: dict[tuple, str] = {}
    for row in rows:
        missing = [d for d in [*dims, "value"] if d not in row]
        if missing:
            raise ValueError(f"{side} row lacks {', '.join(missing)}")
        others = sorted(k for k in row if k != "value")
        key = tuple((k, _key_text(row[k])) for k in others)
        label = ", ".join(f"{k}={row[k]}" for k in others)
        if key in values:
            failures.append(f"{label}: more than 1 {side} row")
            continue
        values[key] = _number(row["value"])
        labels[key] = label
    return values, labels


def prove(
    comparison: Comparison,
    exports: list[dict[str, Any]],
    probe_values: list[dict[str, Any]],
    *,
    twb_xml: str,
    now: datetime | None = None,
) -> Proof:
    """Check that the probe reproduces every exported cell of the sheet.

    Rows on each side are matched on every key except `value`: the
    comparison's dashboard dims, plus any key the caller adds to tell cuts
    apart (such as `cut`). Numeric keys match across types (2026, 2026.0 and
    '2026'). A combination on one side only fails, and so does each matched
    pair that `cell_verdict` does not pass at `comparison.decimals`.

    Args:
        comparison: The comparison; needs `sheet` and `decimals`.
        exports: Export rows mapped to dashboard dim names plus `value`, from
            a copy with the measure's number format dropped.
        probe_values: Probe rows in the same shape, from the dashboard view
            rebuilt as of the refresh the exports read.
        twb_xml: The production workbook XML, for the fingerprint and the
            parameter cuts.
        now: The proof time; defaults to the current UTC time.

    Returns:
        The proof. It is proven only with at least 1 cell and no failures;
        parameter cuts are listed in `browser`, not failed.

    Raises:
        ValueError: `decimals` or `sheet` is unset, a row lacks a dim or
            `value`, or an exported value still carries a number format.
    """
    if comparison.decimals is None:
        raise ValueError(f"comparison {comparison.id!r} has no decimals")
    if not comparison.sheet:
        raise ValueError(f"comparison {comparison.id!r} has no sheet")

    dims = [p.dashboard for p in comparison.dims]
    failures: list[str] = []
    dash, dash_labels = _index(exports, dims, "export", failures)
    probe, probe_labels = _index(probe_values, dims, "probe", failures)

    cells = 0
    for key in sorted(dash.keys() | probe.keys()):
        if key not in probe:
            failures.append(f"{dash_labels[key]}: in the export only")
            continue
        if key not in dash:
            failures.append(f"{probe_labels[key]}: in the probe only")
            continue
        cells += 1
        verdict = cell_verdict(dash[key], probe[key], comparison.decimals)
        if verdict != "pass":
            failures.append(
                f"{dash_labels[key]}: export {dash[key]!r}, probe {probe[key]!r} "
                f"at {comparison.decimals} decimals ({verdict})"
            )
    if not exports:
        failures.append("the export has no rows")

    return Proof(
        fingerprint=formula_fingerprint(twb_xml, comparison.sheet),
        cells=cells,
        failures=failures,
        proven_at=now or datetime.now(timezone.utc),
        browser=split_cuts(comparison.cuts, twb_xml)[1],
    )


# --- Tableau Server ----------------------------------------------------------


def sign_in_from_env() -> TSC.Server:
    """Sign in to Tableau with the personal access token in the environment.

    Reads `TABLEAU_SERVER_ADDRESS`, `TABLEAU_SITE_ID`, `TABLEAU_TOKEN_NAME`
    and `TABLEAU_PERSONAL_ACCESS_TOKEN`; under pytest the secrets fixture in
    `tests/conftest.py` sets them. The caller signs out
    (`server.auth.sign_out()`).

    Returns:
        A signed-in server on REST API 3.25.

    Raises:
        RuntimeError: A variable is unset; the message names the variables,
            never their values.
    """
    missing = [name for name in ENV_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"set {', '.join(missing)} to sign in to Tableau")

    server = TSC.Server(os.environ["TABLEAU_SERVER_ADDRESS"])
    server.version = API_VERSION
    server.auth.sign_in(
        TSC.PersonalAccessTokenAuth(
            token_name=os.environ["TABLEAU_TOKEN_NAME"],
            personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
            site_id=os.environ["TABLEAU_SITE_ID"],
        )
    )
    return server


def _vf_value(value: Any) -> str:
    r"""A view-filter value: a list is an OR-list, `,` and `\\` escaped."""
    values = value if isinstance(value, (list, tuple)) else [value]
    return ",".join(str(v).replace("\\", "\\\\").replace(",", "\\,") for v in values)


def _packaged_twb(archive: zipfile.ZipFile) -> str:
    names = [n for n in archive.namelist() if n.endswith(".twb") and "/" not in n]
    if len(names) != 1:
        raise ValueError(f"expected 1 workbook in the package, found {len(names)}")
    return names[0]


def _bare_lf(text: str) -> int:
    return text.count("\n") - text.count("\r\n")


@dataclass(frozen=True)
class Snapshot:
    """Exports taken with no extract refresh starting in between.

    Attributes:
        refresh_started: Start of the refresh the exports read; the probe
            runs over the dashboard view rebuilt as of this moment.
        copy_luid: The `TEMP-CB` copy the exports came from.
        exports: One list of CSV rows per cut, in the order given.
    """

    refresh_started: datetime
    copy_luid: str
    exports: list[list[dict[str, str]]]


class Tableau:
    """The Tableau reads and the 1 copy a proof needs.

    Args:
        server: A signed-in `tableauserverclient.Server` (see
            `sign_in_from_env`), or a fake with the same attributes.
        now: Returns the current time; defaults to UTC now.
        sign_in: Returns a newly signed-in server, for `reconnect`.
    """

    def __init__(
        self,
        server: Any,
        now: Callable[[], datetime] | None = None,
        sign_in: Callable[[], Any] | None = None,
    ) -> None:
        self._server = server
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._sign_in = sign_in

    def sign_out(self) -> str | None:
        """Sign out; return why it failed instead of raising, so a failure here
        never hides the error that ended the session.
        """
        try:
            self._server.auth.sign_out()
        # Any failure here is reported, not raised: a 401 surfaces as
        # FailedSignInError, which is not a ServerResponseError.
        except Exception as exc:  # noqa: BLE001
            return f"{getattr(exc, 'code', type(exc).__name__)} {getattr(exc, 'summary', exc)}"
        return None

    def reconnect(self) -> None:
        """Sign in again, after Tableau ended this session (a 401).

        Another sign-in with the same token can end it mid-run.
        """
        if self._sign_in is None:
            raise RuntimeError("this session cannot sign in again")
        self.sign_out()
        self._server = self._sign_in()

    def download_twb(self, luid: str) -> str:
        """Return a workbook's XML, downloaded without its extract."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(
                self._server.workbooks.download(
                    luid, filepath=str(Path(tmp) / "workbook"), include_extract=False
                )
            )
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as archive:
                    return archive.read(_packaged_twb(archive)).decode("utf-8")
            return path.read_text(encoding="utf-8", newline="")

    def workbook_updated(self, luid: str) -> datetime:
        """Return when a workbook was last published."""
        return self._server.workbooks.get_by_id(luid).updated_at

    def refresh_started(
        self, workbook_luid: str, since: datetime | None = None
    ) -> datetime:
        """Return the start of the latest successful extract refresh.

        Looks at refreshes of the workbook itself (an embedded extract) and of
        each published data source it connects to. The job list names no
        workbook or data source (its title is empty on this server), so each
        successful refresh job since `since` is looked up with
        `jobs.get_by_id`, newest first, until one belongs to the workbook.

        Args:
            workbook_luid: The production workbook.
            since: Only jobs started at or after this count; defaults to
                `JOB_LOOKBACK` ago, which covers the 7-day time-travel window
                a rebuilt view needs anyway.

        Raises:
            LookupError: No successful refresh of the workbook since `since`
                (as for a workbook on a live connection), or none among the
                newest `MAX_JOB_LOOKUPS` jobs.
        """
        since = since or self._now() - JOB_LOOKBACK
        wb = self._server.workbooks.get_by_id(workbook_luid)
        self._server.workbooks.populate_connections(wb)
        source_ids = {
            c.datasource_id
            for c in wb.connections
            if c.connection_type == "sqlproxy" and c.datasource_id
        }

        # The server parses only this form; str(datetime) is rejected.
        bound = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        candidates = sorted(
            (
                job
                for job in self._server.jobs.filter(
                    status="Success",
                    job_type__in=list(REFRESH_JOB_TYPES),
                    started_at__gte=bound,
                )
                if job.status == "Success"
                and job.type in REFRESH_JOB_TYPES
                and job.started_at is not None
            ),
            key=lambda job: job.started_at,
            reverse=True,
        )
        for job in candidates[:MAX_JOB_LOOKUPS]:
            detail = self._server.jobs.get_by_id(job.id)
            if (
                detail.workbook_id == workbook_luid
                or detail.datasource_id in source_ids
            ):
                return job.started_at
        if len(candidates) > MAX_JOB_LOOKUPS:
            raise LookupError(
                f"no refresh of workbook {wb.name!r} among the newest "
                f"{MAX_JOB_LOOKUPS} refresh jobs since {bound}; the lookup cap "
                "was hit"
            )
        raise LookupError(
            f"no completed extract refresh for workbook {wb.name!r} or its "
            f"published data sources since {bound}"
        )

    def publish_copy(self, workbook_luid: str, xml_edit: Callable[[str], str]) -> str:
        """Publish an edited copy of a workbook to `TEMP-CB`.

        Downloads the workbook with its extract, applies `xml_edit` to the
        packaged `.twb` and publishes the result as `ZZ-VALIDATE <name>` with
        Overwrite, so a rerun replaces the earlier copy. Every other packaged
        file is copied unchanged. Embedded connection credentials are not
        carried; a copy on a live connection cannot query.

        Args:
            workbook_luid: The production workbook.
            xml_edit: Takes and returns the workbook XML, such as
                `lambda x: drop_number_formats(x, measures)`.

        Returns:
            The copy's luid.

        Raises:
            RuntimeError: `TEMP-CB` is not exactly 1 project, or the copy
                landed elsewhere.
            ValueError: The edit is not well-formed XML or flattened CRLF.
        """
        wb = self._server.workbooks.get_by_id(workbook_luid)
        projects = list(self._server.projects.filter(name=TEMP_PROJECT))
        if len(projects) != 1 or projects[0].name != TEMP_PROJECT:
            raise RuntimeError(
                f"expected 1 project named {TEMP_PROJECT}, found {len(projects)}; "
                "the copy goes nowhere else"
            )
        project = projects[0]
        name = f"{COPY_PREFIX}{wb.name}"

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(
                self._server.workbooks.download(
                    workbook_luid,
                    filepath=str(Path(tmp) / "base"),
                    include_extract=True,
                )
            )
            out = Path(tmp) / f"copy{src.suffix}"
            if zipfile.is_zipfile(src):
                with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w") as zout:
                    twb_name = _packaged_twb(zin)
                    for info in zin.infolist():
                        data = zin.read(info)
                        if info.filename == twb_name:
                            data = _edit(data.decode("utf-8"), xml_edit).encode("utf-8")
                        zout.writestr(info, data)
            else:
                text = src.read_text(encoding="utf-8", newline="")
                out.write_text(_edit(text, xml_edit), encoding="utf-8", newline="")

            # The gate runs before the call: a publish overwrites on arrival.
            if project.name != TEMP_PROJECT or not name.startswith(COPY_PREFIX):
                raise RuntimeError("the copy goes only to TEMP-CB as ZZ-VALIDATE")
            item = TSC.WorkbookItem(project_id=project.id, name=name)
            published = self._server.workbooks.publish(
                item, str(out), mode=TSC.Server.PublishMode.Overwrite
            )

        if published.project_id != project.id:
            raise RuntimeError(f"the copy {name!r} landed outside {TEMP_PROJECT}")
        return published.id

    def export(
        self, copy_luid: str, sheet: str, filters: dict[str, Any]
    ) -> list[dict[str, str]]:
        """Export a sheet of the copy as CSV rows, with view filters applied.

        Args:
            copy_luid: The `TEMP-CB` copy.
            sheet: The worksheet name; a dashboard exports no rows.
            filters: `{field caption: value or list of values}`; a list is an
                OR-list. Parameters are not filters: see `split_cuts`.

        Returns:
            One dict per CSV row, keyed by the export's column headers.

        Raises:
            LookupError: The sheet is not a view on the copy; a sheet hidden
                in the workbook does not publish as a view.
        """
        wb = self._server.workbooks.get_by_id(copy_luid)
        self._server.workbooks.populate_views(wb)
        view = next((v for v in wb.views if v.name == sheet), None)
        if view is None:
            raise LookupError(
                f"no view {sheet!r} on the copy; a hidden sheet is not published"
            )

        opts = TSC.CSVRequestOptions()
        for caption, value in filters.items():
            opts.vf(caption, _vf_value(value))
        self._server.views.populate_csv(view, opts)
        text = b"".join(view.csv).decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text, newline="")))

    def capture(
        self,
        workbook_luid: str,
        sheet: str,
        cuts: list[dict[str, Any]],
        xml_edit: Callable[[str], str],
    ) -> Snapshot:
        """Publish the copy and export each cut inside 1 refresh.

        Reads the refresh start before publishing and again after the last
        export. If it moved, the exports may straddle 2 refreshes: they are
        discarded and taken once more.

        Args:
            workbook_luid: The production workbook.
            sheet: The worksheet to export.
            cuts: Exportable cuts (see `split_cuts`); `{}` is the default
                filter state.
            xml_edit: Passed to `publish_copy`.

        Returns:
            The snapshot.

        Raises:
            RefreshMovedError: A refresh started during both attempts.
        """
        for _ in range(2):
            before = self.refresh_started(workbook_luid)
            copy_luid = self.publish_copy(workbook_luid, xml_edit)
            exports = [self.export(copy_luid, sheet, cut) for cut in cuts]
            if self.refresh_started(workbook_luid) == before:
                return Snapshot(before, copy_luid, exports)
        raise RefreshMovedError(
            "an extract refresh started during the exports twice; retry later"
        )


def _edit(text: str, xml_edit: Callable[[str], str]) -> str:
    """Apply an edit, refusing one that breaks the XML or its line endings."""
    edited = xml_edit(text)
    if _bare_lf(edited) and not _bare_lf(text):
        raise ValueError("the edit changed CRLF line endings to bare LF")
    try:
        # trunk-ignore(bandit/B314): workbook XML comes from the org's own Tableau server over authenticated REST; ElementTree resolves no external entities
        ET.fromstring(edited)
    except ET.ParseError as exc:
        raise ValueError(f"the edited workbook is not well-formed XML: {exc}") from exc
    return edited
