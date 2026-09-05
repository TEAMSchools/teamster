r"""Primitives for editing a Tableau .twb inside a .twbx.

Every gotcha this project paid for is encoded here rather than left to the
caller. See HANDOFF.md / README.md for the narrative versions.

  * CRLF is load-bearing. A regex ending '\\n' matches nothing.
  * XML attribute values normalise literal newlines to spaces, so formulas
    must use &#10;.
  * zipfile.writestr(zinfo, ...) MUTATES the ZipInfo it is handed, and those
    objects back the source archive's central directory. Read every payload
    before opening the output or reads fail with "Bad magic number".
  * A colour/format rule keys on a column-INSTANCE name, and the derivation
    must match the one the worksheets use: row-level dimension -> none:,
    aggregate calc -> usr:. A rule with the wrong derivation is kept in the
    file, resolves to a real instance, passes every structural assertion, and
    silently does nothing.
  * A datasource-level colour rule ALSO needs a datasource-level
    <column-instance> or Desktop strips the whole <style> block on next save.
  * Custom number formats need a leading '*': *0.0%, *0.00, *+0.0"PP";...
    Without it Tableau discards the format and renders full precision.
    '#,##0' is accepted either way. 'p1%' is not a real code; 'p0.0%' is.
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

from defusedxml import ElementTree

DERIV_PREFIX = {
    "User": "usr",
    "Avg": "avg",
    "None": "none",
    "Sum": "sum",
    "Min": "min",
    "Attribute": "attr",
    "Count": "count",
}


def esc(s: str) -> str:
    """XML-escape an attribute value. & first; newlines as &#10;."""
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace('"', "&quot;").replace("'", "&apos;")
    return s.replace("\r\n", "&#10;").replace("\n", "&#10;")


def reindent(block: str, extra: int) -> str:
    return "\r\n".join(
        p if not p.strip() else " " * extra + p for p in block.split("\r\n")
    )


class Workbook:
    """A .twbx opened for editing. Text-surgery based, never re-serialised by
    ElementTree -- that would rewrite attribute order across the whole file."""

    def __init__(self, path: Path):
        self.src = Path(path)
        self.zin = zipfile.ZipFile(self.src)
        self.twb_name = next(n for n in self.zin.namelist() if n.endswith(".twb"))
        self.original = self.zin.read(self.twb_name).decode("utf-8")
        self.t = self.original

    # ---- parsing helpers -------------------------------------------------
    @property
    def root(self):
        return ElementTree.fromstring(self.t)

    def ds_element(self, ds_name: str):
        return next(d for d in self.root.iter("datasource") if d.get("name") == ds_name)

    def ds_bounds(self, ds_caption: str, ds_name: str) -> tuple[int, int]:
        s = self.t.index(
            f"<datasource caption='{ds_caption}' inline='true' name='{ds_name}'"
        )
        return s, self.t.index("\r\n    </datasource>", s)

    def caption_map(self, ds_name: str) -> dict:
        """caption -> internal name, including extract columns that have no
        declared <column> (Tableau derives their caption from snake_case)."""
        ds = self.ds_element(ds_name)
        out = {}
        for c in ds.findall("column"):
            if c.get("caption") and c.get("name"):
                out[c.get("caption")] = c.get("name")
        for mr in ds.iter("metadata-record"):
            if mr.get("class") != "column":
                continue
            loc = mr.find("local-name")
            if loc is None or not loc.text:
                continue
            ln = loc.text.strip("[]")
            out.setdefault(" ".join(w.capitalize() for w in ln.split("_")), f"[{ln}]")
        return out

    def param_map(self) -> dict:
        ds = next(
            d for d in self.root.iter("datasource") if d.get("name") == "Parameters"
        )
        return {
            c.get("caption"): c.get("name")
            for c in ds.findall("column")
            if c.get("caption") and c.get("name")
        }

    def next_param_slot(self) -> int:
        used = {int(m) for m in re.findall(r"name='\[Parameter (\d+)\]'", self.t)}
        return max(used) + 1 if used else 1

    @staticmethod
    def instance(
        col_name: str, deriv: str, kind: str, pct_of_total: bool = False
    ) -> str:
        bare = col_name.strip("[]")
        p = DERIV_PREFIX[deriv]
        return f"[pcto:{p}:{bare}:{kind}:2]" if pct_of_total else f"[{p}:{bare}:{kind}]"

    @staticmethod
    def calc_name(caption: str, salt: str = "cf") -> str:
        h = hashlib.sha256(f"{salt}::{caption}".encode()).hexdigest()
        return f"[Calculation_{int(h[:16], 16) % 10**19:019d}]"

    # ---- translation -----------------------------------------------------
    def to_internal(
        self, formula: str, captions: dict[str, str], params: dict[str, str]
    ) -> str:
        """Rewrite a caption-referenced formula into internal ids. Raises on
        anything unresolvable rather than emitting a dangling reference."""
        missing = []

        def repl(m):
            tok = m.group(1)
            if tok in params:
                return f"[Parameters].{params[tok]}"
            if tok in captions:
                return captions[tok]
            missing.append(tok)
            return m.group(0)

        out = re.sub(r"\[([^\[\]]+)\]", repl, formula)
        if missing:
            raise KeyError(f"unresolved references: {sorted(set(missing))}")
        return out

    # ---- mutation --------------------------------------------------------
    def insert(self, at: int, text: str) -> None:
        self.t = self.t[:at] + text + self.t[at:]

    def insert_before(self, anchor: str, text: str, start: int = 0) -> None:
        self.insert(self.t.index(anchor, start), text)

    # ---- verification ----------------------------------------------------
    def check(self) -> None:
        ElementTree.fromstring(self.t)
        if self.t.count("\n") != self.t.count("\r\n"):
            raise ValueError("CRLF broken: a \\r was lost")

    def reverses_to_original(self, chunks: list[str]) -> bool:
        probe = self.t
        for c in chunks:
            if c:
                probe = probe.replace(c, "", 1)
        return probe == self.original

    def audit_colour_rules(self, ds_name: str) -> list[str]:
        """Return colour rules that name an instance no Colour shelf uses.
        This is the check that catches a wrong derivation -- the failure that
        passes every other assertion."""
        r = self.root
        ds = next(d for d in r.iter("datasource") if d.get("name") == ds_name)
        ruled = {
            e.get("field") for e in ds.iter("encoding") if e.get("attr") == "color"
        }
        on_shelf = set()
        for w in r.iter("worksheet"):
            for el in w.iter("color"):
                on_shelf.add((el.get("column") or "").split("].", 1)[-1])
        return sorted(x for x in (ruled - on_shelf) if x)

    def audit_shelf_refs(self, prefix: str = "GPA - ") -> list[tuple]:
        """Every pill on a shelf must resolve to a declared column-instance."""
        bad = []
        for w in self.root.iter("worksheet"):
            if not (w.get("name") or "").startswith(prefix):
                continue
            decl = {ci.get("name") for ci in w.iter("column-instance")}
            for shelf in ("color", "text", "tooltip", "lod"):
                for el in w.iter(shelf):
                    ref = (el.get("column") or "").split("].", 1)[-1]
                    if ref in ("[Multiple Values]", "[:Measure Names]"):
                        continue
                    if ref not in decl:
                        bad.append((w.get("name"), shelf, ref))
            tb = w.find("table")
            for shelf in ("rows", "cols"):
                el = tb.find(shelf) if tb is not None else None
                txt = (el.text or "") if el is not None else ""
                for ref in re.findall(
                    r"\[(?:none|usr|avg|min|sum|attr|pcto)[^\]]*\]", txt
                ):
                    if ref not in decl:
                        bad.append((w.get("name"), shelf, ref))
        return bad

    def audit_geometry(self, only: str | None = None) -> list[str]:
        """Every layout-flow container's children must tile it exactly,
        contiguously, and match on the cross axis.

        ONLY valid on a dashboard we just generated, before Tableau has
        touched it. Tableau's own dashboards do NOT satisfy this -- it adds
        padding and off-by-ones -- and it rewrites the numbers on every
        Desktop round-trip (a 130px row went 14444 -> 15333). Pass `only` to
        scope it to a dashboard by name; calling it bare on a real workbook
        produces hundreds of false positives.
        """
        errs = []

        def walk(z):
            kids = [k for k in z if k.tag == "zone"]
            if kids and z.get("type-v2") == "layout-flow":
                horiz = z.get("param") == "horz"
                dim = "w" if horiz else "h"
                axis = "x" if horiz else "y"
                cross = "h" if horiz else "w"
                span = sum(int(k.get(dim)) for k in kids)
                if span != int(z.get(dim)):
                    errs.append(
                        f"{z.get('friendly-name') or z.get('id')}: "
                        f"children {dim} sum {span} != {z.get(dim)}"
                    )
                pos = int(z.get(axis))
                for k in kids:
                    if int(k.get(axis)) != pos:
                        errs.append(
                            f"{z.get('friendly-name')}: gap at "
                            f"{k.get('name') or k.get('id')}"
                        )
                    pos += int(k.get(dim))
                    if int(k.get(cross)) != int(z.get(cross)):
                        errs.append(
                            f"{z.get('friendly-name')}: {cross} "
                            f"mismatch on {k.get('name')}"
                        )
            for k in kids:
                walk(k)

        for d in self.root.iter("dashboard"):
            if only is not None and d.get("name") != only:
                continue
            for zs in d.iter("zones"):
                for z in zs:
                    walk(z)
        return errs

    # ---- output ----------------------------------------------------------
    def save(self, out: Path) -> Path:
        """Repackage. Reads every payload BEFORE opening the output, and
        writes fresh ZipInfo objects -- see the module docstring."""
        out = Path(out)
        payloads = {n: self.zin.read(n) for n in self.zin.namelist()}
        payloads[self.twb_name] = self.t.encode("utf-8")
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
            for item in self.zin.infolist():
                fresh = zipfile.ZipInfo(item.filename, date_time=item.date_time)
                fresh.compress_type = item.compress_type
                fresh.external_attr = item.external_attr
                fresh.create_system = item.create_system
                zo.writestr(fresh, payloads[item.filename])
        # non-.twb entries must be byte-identical
        zc = zipfile.ZipFile(out)
        if zc.namelist() != self.zin.namelist():
            raise ValueError("package entry list changed")
        for n in self.zin.namelist():
            if n == self.twb_name:
                continue
            a = hashlib.sha256(zc.read(n)).hexdigest()
            b = hashlib.sha256(payloads[n]).hexdigest()
            if a != b:
                raise ValueError(f"non-twb entry changed: {n}")
        return out
