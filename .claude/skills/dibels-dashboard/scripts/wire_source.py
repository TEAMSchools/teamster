"""Edit exactly one source block in sources-external.yml, bounded by the next
source at the same indent. No forward-scanning regex."""

import pathlib


def block_bounds(lines, source_name):
    start = next(
        i
        for i, line in enumerate(lines)
        if line.rstrip("\n") == f"      - name: {source_name}"
    )
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("      - name: src_"):
            end = i
            break
    return start, end


def wire(path, source_name, new_range, cols):
    p = pathlib.Path(path)
    lines = p.read_text().splitlines(keepends=True)
    s, e = block_bounds(lines, source_name)
    blk = lines[s:e]

    # 1. sheet_range, within this block only
    hits = [i for i, line in enumerate(blk) if line.strip().startswith("sheet_range:")]
    if len(hits) != 1:
        raise ValueError(f"{source_name}: {len(hits)} sheet_range lines")
    blk[hits[0]] = f"            sheet_range: {new_range}\n"

    # 2. columns block, within this block only
    coltxt = "".join(
        f"          - name: {n}\n            data_type: {t}\n" for n, t in cols
    )
    cidx = [i for i, line in enumerate(blk) if line.rstrip("\n") == "        columns:"]
    if len(cidx) > 1:
        raise ValueError(f"{source_name}: {len(cidx)} columns blocks")
    if cidx:
        c = cidx[0]
        j = c + 1
        while j < len(blk) and blk[j].startswith("          "):
            j += 1
        blk[c:j] = ["        columns:\n"] + coltxt.splitlines(keepends=True)
    else:
        # insert right after the external: options block, before config:
        cfg = next(
            i for i, line in enumerate(blk) if line.rstrip("\n") == "        config:"
        )
        blk[cfg:cfg] = ["        columns:\n"] + coltxt.splitlines(keepends=True)

    lines[s:e] = blk
    p.write_text("".join(lines))
    print(f"{source_name}: range -> {new_range}, {len(cols)} columns")
