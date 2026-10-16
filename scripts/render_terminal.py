#!/usr/bin/env python3
"""Turn a captured terminal run (assets/projects/src/<name>.ansi) into an HTML terminal window.

The .ansi files are the unedited output of the commands named in SHOTS, run for real
(see docs/MAINTAINING.md). This script only picks line ranges, wraps long lines the way a
terminal of COLS columns would, and maps the colour codes to a palette. Screenshot the HTML
at 2x to get assets/projects/<name>.png:

    python3 scripts/render_terminal.py            # writes build/terminal/<name>.html
"""

from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "projects" / "src"
OUT = ROOT / "build" / "terminal"
COLS = 94

ANSI = {"30": "#5C6370", "31": "#FF6B6B", "32": "#4FD69C", "33": "#FFC857", "34": "#6CB6FF", "35": "#D58CFF",
        "36": "#5CD6E0", "37": "#E6E6E6", "90": "#7D8590", "91": "#FF5F6D", "92": "#6EE7A8", "93": "#FFD866",
        "94": "#8CC8FF", "95": "#E3A6FF", "96": "#7FE3EC", "97": "#FFFFFF"}
ANSI_BG = {"41": "#FF4D5E", "42": "#3DDC97", "43": "#FFC24A", "44": "#5AA9FF", "45": "#B04CE0"}

# name: (command shown in the prompt, line ranges of the capture to show (1-based, inclusive), colours)
SHOTS = {
    "hexvero": ("npx hexvero analyze examples/notesdesk-1.4.0.asar", [(1, 12)],
                dict(bg="#1B1D21", bar="#25282D", fg="#E6E3DC", accent="#F2B84B")),
    "spillage": ("spillage scan   # a throwaway home with the fake keys from its test suite", [(2, 12)],
                 dict(bg="#0E0F13", bar="#191A20", fg="#E9E7E2", accent="#FF6B4A")),
    "dockdu": ("docker run --rm … ghcr.io/maximilianfeix/dockdu:v0.5.0 --top 3", [(1, 13)],
               dict(bg="#141E27", bar="#1B2733", fg="#E6EEF2", accent="#36B6C5")),
}

SGR = re.compile(r"\x1b\[([0-9;]*)m")


def cells(line: str) -> list[tuple[str, tuple]]:
    """Characters with their style: (fg, bg, bold, dim)."""
    out, fg, bg, bold, dim, pos = [], None, None, False, False, 0
    for m in list(SGR.finditer(line)) + [None]:
        end = m.start() if m else len(line)
        out += [(ch, (fg, bg, bold, dim)) for ch in line[pos:end]]
        if not m:
            break
        for code in (m.group(1) or "0").split(";"):
            if code in ("0", ""):
                fg, bg, bold, dim = None, None, False, False
            elif code == "1":
                bold = True
            elif code == "2":
                dim = True
            elif code in ("22",):
                bold = dim = False
            elif code == "39":
                fg = None
            elif code == "49":
                bg = None
            elif code in ANSI:
                fg = ANSI[code]
            elif code in ANSI_BG:
                bg = ANSI_BG[code]
        pos = m.end()
    return out


def wrap(row: list) -> list[list]:
    if len(row) <= COLS:
        return [row]
    # wrap at the last space before the edge and indent the rest, so a long line still reads as one
    indent = len(row) - len("".join(c for c, _ in row).lstrip(" "))
    lines, rest, width = [], row, COLS
    while len(rest) > width:
        cut = max((i for i in range(indent + 1, width) if rest[i][0] == " "), default=width)
        lines.append(rest[:cut])
        rest = rest[cut:]
        while rest and rest[0][0] == " ":
            rest = rest[1:]
        rest = [(" ", (None, None, False, False))] * indent + rest
    return lines + [rest]


def render_row(row: list) -> str:
    out, run, style = [], "", None
    for ch, st in row + [("", None)]:
        if st != style and run:
            fg, bg, bold, dim = style
            css = []
            if fg:
                css.append(f"color:{fg}")
            if bg:
                css.append(f"background:{bg};color:#0E0F13")
            if bold:
                css.append("font-weight:600")
            if dim:
                css.append("opacity:.6")
            out.append(f'<span style="{";".join(css)}">{html.escape(run)}</span>' if css else html.escape(run))
            run = ""
        style = st
        run += ch
    return "".join(out)


def page(name: str) -> str:
    cmd, ranges, c = SHOTS[name]
    lines = (SRC / f"{name}.ansi").read_text(encoding="utf-8").replace("\r", "").split("\n")
    rows = []
    for i, (a, b) in enumerate(ranges):
        if i:
            rows.append('<span style="opacity:.45">  ⋮</span>')
        for line in lines[a - 1:b]:
            rows += [render_row(r) for r in wrap(cells(line))]
    while rows and not re.sub("<[^>]+>", "", rows[-1]).strip():
        rows.pop()
    font = (ROOT / "fonts" / "GeistMono-Regular.ttf").as_uri()
    prompt = f'<span style="color:{c["accent"]}">$</span> {html.escape(cmd)}'
    return f"""<!doctype html><meta charset="utf-8">
<style>
@font-face {{ font-family: GM; src: url("{font}"); }}
html, body {{ margin: 0; background: transparent; }}
.win {{ width: {COLS * 9.0 + 56:.0f}px; background: {c["bg"]}; border-radius: 12px; overflow: hidden;
  border: 1px solid rgba(255,255,255,.08); font: 15px/1.55 GM, ui-monospace, monospace; color: {c["fg"]};
  font-variant-ligatures: none; font-feature-settings: "liga" 0, "calt" 0; }}
.bar {{ height: 34px; background: {c["bar"]}; display: flex; align-items: center; gap: 8px; padding: 0 16px; }}
.bar i {{ width: 11px; height: 11px; border-radius: 50%; background: rgba(255,255,255,.16); }}
.bar b {{ margin-left: auto; margin-right: auto; font: 13px GM; color: rgba(255,255,255,.45); font-weight: 400; }}
pre {{ margin: 0; padding: 18px 28px 22px; font: inherit; white-space: pre; }}
</style>
<div class="win" id="shot"><div class="bar"><i></i><i></i><i></i><b>{name}</b></div>
<pre>{prompt}
{chr(10).join(rows)}</pre></div>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in SHOTS:
        (OUT / f"{name}.html").write_text(page(name), encoding="utf-8")
        print(OUT / f"{name}.html")


if __name__ == "__main__":
    main()
