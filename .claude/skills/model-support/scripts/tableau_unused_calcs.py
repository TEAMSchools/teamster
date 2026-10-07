"""List a Tableau workbook's unused calculated fields, in a safe delete order.

Usage: uv run python tableau_unused_calcs.py <workbook.twb | workbook.twbx>

A calc is used when anything outside its own definition names it: a
worksheet, dashboard, action, datasource filter, group, or set. Hits inside
<windows> (saved state for hidden sheets) and in datasource-level
<column-instance> and <style> entries (left behind after a field's last sheet
stops using it) do not count. A calc
referenced only by other unused calcs is unused too, and is deleted after them.

Prints the unused calcs as numbered delete steps (a calc always comes after
every calc that reads it, so Tableau never warns about dependents), then any
kept calc whose internal name echoes a deleted caption.
"""

import re
import sys

# trunk-ignore(bandit/B405): parses workbooks the user downloaded from their own Tableau site
import xml.etree.ElementTree as ET
import zipfile


def load_root(path):
    if path.endswith(".twbx"):
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.endswith(".twb"))
            # trunk-ignore(bandit/B314): see the B405 note at the import
            return ET.fromstring(z.read(name))
    # trunk-ignore(bandit/B314): see the B405 note at the import
    return ET.parse(path).getroot()


def ref_pattern(key):
    # [key] in formulas and filters, :key: inside instance names such as
    # [none:Calculation_123:nk]
    k = re.escape(key)
    return re.compile(r"\[" + k + r"\]|:" + k + r":")


def analyse(root):
    datasources = root.find("datasources")
    calcs = {}
    for ds in [] if datasources is None else datasources:
        if ds.get("name") == "Parameters":
            continue
        dsn = ds.get("caption") or ds.get("name")
        for col in ds.findall("column"):
            calc = col.find("calculation")
            if calc is None or calc.get("formula") is None:
                continue
            key = col.get("name", "").strip("[]")
            calcs[key] = {
                "caption": col.get("caption") or key,
                "formula": calc.get("formula"),
                "datasource": dsn,
            }

    # everything except the calc definitions themselves, <windows>, and the
    # datasource-level <column-instance> and <style> entries, which outlive the
    # last sheet that used a field (Tableau deletes such a field without a
    # warning)
    outside = []
    for child in root:
        if child.tag == "windows":
            continue
        if child.tag == "datasources":
            for ds in child:
                for el in ds:
                    is_calc_def = (
                        el.tag == "column"
                        and el.get("name", "").strip("[]") in calcs
                        and el.find("calculation") is not None
                    )
                    if not is_calc_def and el.tag not in ("column-instance", "style"):
                        outside.append(ET.tostring(el, encoding="unicode"))
            continue
        outside.append(ET.tostring(child, encoding="unicode"))
    outside_text = "\n".join(outside)

    patterns = {k: ref_pattern(k) for k in calcs}
    reads = {
        k: {o for o in calcs if o != k and patterns[o].search(v["formula"])}
        for k, v in calcs.items()
    }

    used = set()
    stack = [k for k in calcs if patterns[k].search(outside_text)]
    while stack:
        k = stack.pop()
        if k in used:
            continue
        used.add(k)
        stack.extend(reads[k])

    unused = set(calcs) - used
    order = []
    remaining = set(unused)
    while remaining:
        # deletable now: no remaining unused calc reads it
        ready = sorted(
            (k for k in remaining if not any(k in reads[o] for o in remaining)),
            key=lambda k: calcs[k]["caption"].lower(),
        )
        if not ready:  # a cycle; list the rest together
            ready = sorted(remaining, key=lambda k: calcs[k]["caption"].lower())
        order.extend(ready)
        remaining -= set(ready)

    deleted_captions = {calcs[k]["caption"].lower() for k in unused}
    lookalikes = [
        k
        for k in used
        if k.lower() != calcs[k]["caption"].lower()
        and any(c in k.lower() for c in deleted_captions)
    ]
    return calcs, order, sorted(lookalikes), reads


def main(path):
    calcs, order, lookalikes, reads = analyse(load_root(path))
    if not order:
        print("No unused calculated fields.")
        return
    print(f"{len(order)} unused calculated fields. Delete in this order:")
    for i, k in enumerate(order, 1):
        c = calcs[k]
        readers = sorted(calcs[o]["caption"] for o in order if k in reads[o])
        after = f"  (after {', '.join(readers)})" if readers else ""
        print(f"{i:>3}. {c['caption']}  [{c['datasource']}]{after}")
    for k in lookalikes:
        print(
            f"KEEP: {calcs[k]['caption']} is still used; its internal name "
            f"'{k}' looks like a field being deleted."
        )


if __name__ == "__main__":
    main(sys.argv[1])
