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


def graphql(query: str):
    req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps({"query": query}).encode(),
                                 headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "User-Agent": USER})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["data"]


@dataclass
class Profile:
    repos: int = 0
    stars: int = 0
    followers: int = 0
    release: str = ""
    live_proxies: str = ""
    repo_stars: dict = field(default_factory=dict)
    atlas_release: str = ""
    weeks: list = field(default_factory=list)
    week_starts: list = field(default_factory=list)
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

    try:
        cal = graphql("{user(login: \"%s\") {contributionsCollection {contributionCalendar "
                      "{weeks {contributionDays {date contributionCount}}}}}}" % USER)
        for w in cal["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            days = w["contributionDays"]
            p.weeks.append(sum(d["contributionCount"] for d in days))
            p.week_starts.append(days[0]["date"])
    except Exception as e:
        print(f"contribution calendar unavailable: {e}", file=sys.stderr)

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
    "light": dict(bg="#FBFBFA", ink="#16171A", muted="#5C5F66", faint="#8E9198", rule="#E3E3DF",
                  bar="#C9CBCF", accent="#4D7C0F", border="#E3E3DF"),
    "dark": dict(bg="#141416", ink="#EDEBE4", muted="#A3A29D", faint="#6F6E6A", rule="#2B2B2F",
                 bar="#4A4A4F", accent="#C6F36B", border="#26262A"),
}
SANS, SANS_B, MONO, MONO_M = "IBMPlexSans-Regular", "IBMPlexSans-SemiBold", "IBMPlexMono-Regular", "IBMPlexMono-Medium"


def fmt_int(n: int) -> str:
    return f"{n:,}"


def render_header(p: Profile, theme: str) -> str:
    c = THEMES[theme]
    W, H = 1200, 300
    out = [f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="{c["bg"]}" stroke="{c["border"]}"/>']

    # left: who, what, with what
    out.append(text("Maximilian Feix", 56, 112, SANS_B, 54, c["ink"], tracking=-0.4))
    out.append(text("Backend and infrastructure at a hosting company in Germany.", 57, 160, SANS, 21, c["muted"]))
    out.append(spans([("Author of ", SANS, c["muted"]), ("proxy-scraper", SANS_B, c["ink"]),
                      (" and ", SANS, c["muted"]), ("RepoAtlas", SANS_B, c["ink"]), (".", SANS, c["muted"])],
                     57, 190, 21))
    out.append(f'<line x1="57" y1="228" x2="560" y2="228" stroke="{c["rule"]}"/>')
    out.append(text("   ".join(STACK), 57, 256, MONO, 14, c["faint"]))

    # right: the last year of real activity, one bar per week
    weeks = p.weeks or [0] * 53
    cx, cw, top, base = 660, 484, 92, 214
    n = len(weeks)
    gap = 2.2
    bw = (cw - gap * (n - 1)) / n
    peak = max(weeks) or 1
    total = sum(weeks)
    out.append(spans([(fmt_int(total), MONO_M, c["ink"]), (" contributions in the last year", MONO, c["faint"])],
                     cx, 64, 14))
    for i, v in enumerate(weeks):
        h = (base - top) * (v / peak) ** 0.5 if v else 0  # square root, so quiet weeks stay visible
        x = cx + i * (bw + gap)
        fill = c["accent"] if i == n - 1 else c["bar"]
        if h:
            out.append(f'<rect x="{x:.1f}" y="{base - max(h, 2):.1f}" width="{bw:.1f}" height="{max(h, 2):.1f}" fill="{fill}"/>')
        else:
            out.append(f'<rect x="{x:.1f}" y="{base - 1:.1f}" width="{bw:.1f}" height="1" fill="{c["rule"]}"/>')
    out.append(f'<line x1="{cx}" y1="{base + .5}" x2="{cx + cw}" y2="{base + .5}" stroke="{c["rule"]}"/>')
    # quarter ticks from the calendar's own dates
    last_month = None
    for i, d in enumerate(p.week_starts):
        m = d[5:7]
        if m != last_month and m in ("01", "04", "07", "10") and 0 < i < n - 3:
            label = datetime.strptime(d, "%Y-%m-%d").strftime("%b")
            out.append(text(label, cx + i * (bw + gap), base + 22, MONO, 12, c["faint"]))
        last_month = m
    out.append(text("weekly, square-root scale", cx + cw, 256, MONO, 12, c["faint"], anchor="end"))
    updated = p.now.strftime("%d %b %Y")
    out.append(text(f"updated {updated}", cx, 256, MONO, 12, c["faint"]))

    label = (f"Maximilian Feix. Backend and infrastructure at a hosting company in Germany. "
             f"Author of proxy-scraper and RepoAtlas. {fmt_int(total)} contributions in the last year.")
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
