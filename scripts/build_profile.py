#!/usr/bin/env python3
"""Build the dynamic parts of the profile.

- assets/header-dark.svg / header-light.svg: banner with a live status panel
- assets/card-<repo>.svg: featured project cards, a real screenshot plus live numbers
- README.md: the "Recently shipped" list between the SHIPPED markers

Only public data is used. Runs in GitHub Actions (see .github/workflows/profile.yml),
works locally too: `pip install -r scripts/requirements.txt`, then
`GITHUB_TOKEN=$(gh auth token) python3 scripts/build_profile.py`.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from pathlib import Path

USER = "maximilianfeix"
FEATURED = "proxy-scraper"
ATLAS = "repoatlas"
SKIP_REPOS = {"community-content", USER}
ROOT = Path(__file__).resolve().parent.parent

STACK = ["TypeScript", "Node.js", "PHP", "Python", "Linux"]


def get(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": USER})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com"):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


@dataclass
class Profile:
    repos: int = 0
    stars: int = 0
    followers: int = 0
    release: str = ""
    live_proxies: str = ""
    repo_stars: dict = field(default_factory=dict)
    atlas_release: str = ""
    shipped: list = field(default_factory=list)
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def collect() -> Profile:
    p = Profile()
    p.followers = get(f"https://api.github.com/users/{USER}")["followers"]
    repos = [r for r in get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
             if not r["fork"] and not r["private"] and r["name"] not in SKIP_REPOS]
    p.repos = len(repos)
    public = {r["name"] for r in repos}
    p.stars = sum(r["stargazers_count"] for r in repos)
    p.repo_stars = {r["name"]: r["stargazers_count"] for r in repos}

    try:
        p.release = get(f"https://api.github.com/repos/{USER}/{FEATURED}/releases/latest")["tag_name"]
    except Exception:
        pass
    try:
        p.atlas_release = get(f"https://api.github.com/repos/{USER}/{ATLAS}/releases/latest")["tag_name"]
    except Exception:
        pass
    try:
        badge = get(f"https://raw.githubusercontent.com/{USER}/{FEATURED}/proxy-list/badges/total.json")
        p.live_proxies = badge["message"]
    except Exception:
        pass

    items = []
    for r in repos:
        for rel in get(f"https://api.github.com/repos/{USER}/{r['name']}/releases?per_page=5"):
            if not rel["draft"]:
                items.append((rel["published_at"], f"🏷️ Released **[{r['name']} {rel['tag_name']}]({rel['html_url']})**"))
    query = f"is:pr+is:merged+author:{USER}+user:{USER}"
    for pr in get(f"https://api.github.com/search/issues?q={query}&sort=updated&order=desc&per_page=20")["items"]:
        repo = pr["repository_url"].rsplit("/", 1)[-1]
        if repo not in public:  # never list anything from private repos
            continue
        title = pr["title"].replace("[", "(").replace("]", ")")
        items.append((pr["closed_at"], f"🔀 Merged [{title}]({pr['html_url']}) in **{repo}**"))
    items.sort(reverse=True)
    p.shipped = items[:6]
    return p


# ---------------------------------------------------------------- typesetting
# Text is shaped with HarfBuzz and written out as outlines, so the banner looks the
# same everywhere: GitHub serves SVGs as images, which can't load web fonts reliably.

FONTS = ROOT / "fonts"
_faces: dict = {}


def _face(name: str):
    if name not in _faces:
        import uharfbuzz as hb
        from fontTools.ttLib import TTFont
        data = (FONTS / f"{name}.ttf").read_bytes()
        font = hb.Font(hb.Face(data))
        tt = TTFont(FONTS / f"{name}.ttf")
        _faces[name] = (font, tt.getGlyphSet(), tt["head"].unitsPerEm, tt.getGlyphOrder())
    return _faces[name]


def text_width(s: str, font: str, size: float, tracking: float = 0) -> float:
    return _shape(s, font, size, tracking)[1]


def _shape(s: str, font: str, size: float, tracking: float):
    import uharfbuzz as hb
    hbfont, _, upem, order = _face(font)
    buf = hb.Buffer()
    buf.add_str(s)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf, {"kern": True, "liga": True})
    scale = size / upem
    glyphs, x = [], 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        glyphs.append((order[info.codepoint], x + pos.x_offset * scale, pos.y_offset * scale))
        x += pos.x_advance * scale + tracking
    return glyphs, x - tracking if glyphs else 0.0


def text(s: str, x: float, y: float, font: str, size: float, fill: str,
         anchor: str = "start", tracking: float = 0) -> str:
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    _, glyphset, upem, _ = _face(font)
    glyphs, width = _shape(s, font, size, tracking)
    x0 = x - {"start": 0, "middle": width / 2, "end": width}[anchor]
    scale = size / upem
    pen = SVGPathPen(glyphset, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
    for name, gx, gy in glyphs:
        glyphset[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x0 + gx, y - gy)))
    d = pen.getCommands()
    return f'<path fill="{fill}" d="{d}"><title>{escape(s)}</title></path>' if d else ""


def spans(parts: list, x: float, y: float, size: float) -> str:
    """Several runs on one baseline, e.g. a number in ink followed by a muted label."""
    out = []
    for s, font, fill in parts:
        out.append(text(s, x, y, font, size, fill))
        x += text_width(s, font, size)
    return "".join(out)


# ---------------------------------------------------------------- header

THEMES = {
    # no background: the header sits on GitHub's own page colour, like a masthead
    "light": dict(ink="#121113", muted="#57564F", faint="#7E7D77", rule="#D0D7DE", signal="#3F5A00"),
    "dark": dict(ink="#EDEBE6", muted="#A6A59F", faint="#7D7C77", rule="#30363D", signal="#D4F77A"),
}
DISPLAY, SANS, SANS_B = "Geist-SemiBold", "Geist-Regular", "Geist-SemiBold"
MONO, MONO_M = "GeistMono-Regular", "GeistMono-Regular"


def fmt_int(n: int) -> str:
    return f"{n:,}"


def render_header(p: Profile, theme: str) -> str:
    c = THEMES[theme]
    W, H = 1200, 340
    out = []

    # the name, set like the proxy-scraper site's headline
    name, size = "Maximilian Feix", 128
    out.append(text(name, -4, 128, DISPLAY, size, c["ink"], tracking=-5.2))
    out.append(text(".", -4 + text_width(name, DISPLAY, size, -5.2) + 1, 128, DISPLAY, size, c["signal"]))

    out.append(text("Backend and infrastructure at a hosting company in Germany.", 0, 196, SANS, 28, c["muted"]))
    out.append(spans([("Currently shipping ", SANS, c["muted"]), ("proxy-scraper", SANS_B, c["ink"]),
                      (" and ", SANS, c["muted"]), ("RepoAtlas", SANS_B, c["ink"]), (".", SANS, c["muted"])],
                     0, 236, 28))

    out.append(f'<rect y="282" width="{W}" height="1" fill="{c["rule"]}"/>')
    out.append(text("   ".join(STACK), 0, 320, MONO, 17, c["faint"]))
    if p.live_proxies:
        live = f"{p.live_proxies} proxies verified this hour"
        out.append(text(live, W, 320, MONO, 17, c["muted"], anchor="end"))
        out.append(f'<circle cx="{W - text_width(live, MONO, 17) - 15}" cy="314.5" r="4" fill="{c["signal"]}"/>')

    label = ("Maximilian Feix. Backend and infrastructure at a hosting company in Germany. "
             "Currently shipping proxy-scraper and RepoAtlas.")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="{escape(label)}">\n' + "\n".join(out) + "\n</svg>\n")


# ---------------------------------------------------------------- project cards
# Each card wears its project's own colours and shows a real screenshot of it.

@dataclass
class Card:
    slug: str
    title: str
    lang: str
    tagline: str
    facts: list  # (text, emphasised)
    shot: str  # raw URL of a screenshot in the project's repo
    crop: tuple  # left, top, right, bottom as fractions of the screenshot
    colors: dict


def cards(p: Profile) -> list[Card]:
    raw = f"https://raw.githubusercontent.com/{USER}"
    return [
        Card(FEATURED, "proxy-scraper", "Python",
             "Scrapes 700+ sources and keeps only proxies that pass real checks.",
             [(p.live_proxies or "1,000+", True), (" verified this hour", False),
              ("   ·   ", False), (p.release or "latest", False)],
             f"{raw}/{FEATURED}/main/docs/website.png", (0.055, 0.17, 0.96, 0.785),
             dict(bg="#141416", ink="#EDEBE4", muted="#9C9B96", accent="#C6F36B", rule="#2A2A2E")),
        Card(ATLAS, "RepoAtlas", "TypeScript",
             "An architecture map of any TypeScript repo, every import traced to its line.",
             [("npx", True), (", one offline HTML file", False), ("   ·   ", False), (p.atlas_release or "latest", False)],
             f"{raw}/{ATLAS}/main/docs/assets/architecture-map-preview.png", (0.142, 0.24, 0.8, 1.0),
             dict(bg="#101722", ink="#E7EDF6", muted="#8C99AB", accent="#8BDEC1", rule="#223044")),
    ]


def screenshot(card: Card, w: int, h: int) -> str:
    """Fetch, crop to the frame's aspect ratio and embed as JPEG (SVG images can't load URLs)."""
    import base64
    import io
    from PIL import Image
    with urllib.request.urlopen(card.shot, timeout=30) as resp:
        img = Image.open(io.BytesIO(resp.read())).convert("RGB")
    l, t, r, b = card.crop
    box = [img.width * l, img.height * t, img.width * r, img.height * b]
    want = w / h
    bw, bh = box[2] - box[0], box[3] - box[1]
    if bw / bh > want:  # too wide: trim the sides evenly
        cut = (bw - bh * want) / 2
        box[0] += cut; box[2] -= cut
    else:  # too tall: keep the top
        box[3] = box[1] + bw / want
    img = img.crop(tuple(round(v) for v in box)).resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def render_card(card: Card) -> str:
    c = card.colors
    W, IH, CH = 960, 540, 190
    H = IH + CH
    href = screenshot(card, W, IH)
    y = IH
    facts, x = [], 40
    for s, strong in card.facts:
        facts.append(text(s, x, y + 150, MONO_M if strong else MONO, 19, c["accent"] if strong else c["muted"]))
        x += text_width(s, MONO_M if strong else MONO, 19)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{escape(card.title)}: {escape(card.tagline)}">
<defs><clipPath id="r"><rect width="{W}" height="{H}" rx="12"/></clipPath></defs>
<g clip-path="url(#r)">
<rect width="{W}" height="{H}" fill="{c["bg"]}"/>
<image href="{href}" width="{W}" height="{IH}" preserveAspectRatio="xMidYMin slice"/>
<rect y="{IH}" width="{W}" height="1" fill="{c["rule"]}"/>
{text(card.title, 40, y + 62, SANS_B, 36, c["ink"], tracking=-0.3)}
{text(card.lang, W - 40, y + 60, MONO, 17, c["muted"], anchor="end")}
{text(card.tagline, 40, y + 104, SANS, 21, c["muted"])}
{"".join(facts)}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="none" stroke="{c["rule"]}"/>
</svg>
"""


def render_shipped(p: Profile) -> str:
    if not p.shipped:
        return "_Nothing new this week._"
    out = []
    for when, text in p.shipped:
        date = datetime.fromisoformat(when.replace("Z", "+00:00")).strftime("%d %b %Y")
        out.append(f"- {text} <sub>· {date}</sub>")
    return "\n".join(out)


def replace_section(text: str, name: str, body: str) -> str:
    pattern = re.compile(rf"(<!--{name}:start-->).*?(<!--{name}:end-->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"marker {name} missing in README.md")
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)


def main() -> int:
    p = collect()
    for theme in THEMES:
        (ROOT / "assets" / f"header-{theme}.svg").write_text(render_header(p, theme), encoding="utf-8")
    for card in cards(p):
        (ROOT / "assets" / f"card-{card.slug}.svg").write_text(render_card(card), encoding="utf-8")
    readme = ROOT / "README.md"
    readme.write_text(replace_section(readme.read_text(encoding="utf-8"), "SHIPPED", render_shipped(p)), encoding="utf-8")
    print(f"repos={p.repos} stars={p.stars} followers={p.followers} release={p.release} "
          f"atlas={p.atlas_release} live={p.live_proxies} shipped={len(p.shipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
