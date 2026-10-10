#!/usr/bin/env python3
"""Build the dynamic parts of the profile.

- assets/header-dark.svg / header-light.svg: banner with a live status panel
- assets/card-<repo>.svg: featured project cards, a real screenshot plus live numbers
- assets/activity-dark.svg / activity-light.svg: releases, contributions and languages
- README.md: the "Recently shipped" and "Open source" lists between their markers

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
SPILLAGE = "spillage"
PREVIEW = "gha-preview"
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


def gql(query: str) -> dict:
    req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps({"query": query}).encode(),
                                 headers={"User-Agent": USER, "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"})
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
    spillage_release: str = ""
    preview_release: str = ""
    contrib: list = field(default_factory=list)  # (full_name, stars, merged PR count)
    releases: int = 0
    languages: list = field(default_factory=list)  # (name, share of bytes in percent), largest first
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
    for repo, attr in [(ATLAS, "atlas_release"), (SPILLAGE, "spillage_release"), (PREVIEW, "preview_release")]:
        try:
            setattr(p, attr, get(f"https://api.github.com/repos/{USER}/{repo}/releases/latest")["tag_name"])
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
                items.append((rel["published_at"], r["name"],
                              f"🏷️ Released **[{r['name']} {rel['tag_name']}]({rel['html_url']})**"))
    query = f"is:pr+is:merged+author:{USER}+user:{USER}"
    for pr in get(f"https://api.github.com/search/issues?q={query}&sort=updated&order=desc&per_page=50")["items"]:
        repo = pr["repository_url"].rsplit("/", 1)[-1]
        if repo not in public:  # never list anything from private repos
            continue
        title = pr["title"].replace("[", "(").replace("]", ")")
        items.append((pr["closed_at"], repo, f"🔀 Merged [{title}]({pr['html_url']}) in **{repo}**"))
    items.sort(reverse=True)
    per_repo: dict = {}
    for when, repo, line in items:  # at most two per repo, so one busy project doesn't fill the list
        per_repo[repo] = per_repo.get(repo, 0) + 1
        if per_repo[repo] <= 2 and len(p.shipped) < 6:
            p.shipped.append((when, line))

    # merged pull requests in other people's projects
    counts: dict = {}
    query = f"is:pr+is:merged+author:{USER}+-user:{USER}"
    for page in range(1, 11):  # the search API stops at 1,000 results
        found = get(f"https://api.github.com/search/issues?q={query}&per_page=100&page={page}")["items"]
        for pr in found:
            name = pr["repository_url"].split("/repos/", 1)[1]
            counts[name] = counts.get(name, 0) + 1
        if len(found) < 100:
            break
    for name, n in counts.items():
        try:
            repo = get(f"https://api.github.com/repos/{name}")
        except Exception:
            continue
        if not repo["private"]:
            p.contrib.append((repo["full_name"], repo["stargazers_count"], n))
    p.contrib.sort(key=lambda c: (-c[1], c[0]))

    nodes = gql(f'''{{ user(login: "{USER}") {{ repositories(ownerAffiliations: OWNER, isFork: false,
        privacy: PUBLIC, first: 100) {{ nodes {{ name releases {{ totalCount }}
        languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{ edges {{ size node {{ name }} }} }}
        }} }} }} }}''')["user"]["repositories"]["nodes"]
    sizes: dict = {}
    for r in nodes:
        if r["name"] in SKIP_REPOS:
            continue
        p.releases += r["releases"]["totalCount"]
        for e in r["languages"]["edges"]:
            sizes[e["node"]["name"]] = sizes.get(e["node"]["name"], 0) + e["size"]
    total = sum(sizes.values()) or 1
    p.languages = sorted(((n, v / total * 100) for n, v in sizes.items()), key=lambda l: -l[1])
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
                      (", ", SANS, c["muted"]), ("spillage", SANS_B, c["ink"]),
                      (" and ", SANS, c["muted"]), ("RepoAtlas", SANS_B, c["ink"]), (".", SANS, c["muted"])],
                     0, 236, 28))

    out.append(f'<rect y="282" width="{W}" height="1" fill="{c["rule"]}"/>')
    out.append(text("   ".join(STACK), 0, 320, MONO, 17, c["faint"]))
    if p.live_proxies:
        live = f"{p.live_proxies} proxies verified this hour"
        out.append(text(live, W, 320, MONO, 17, c["muted"], anchor="end"))
        out.append(f'<circle cx="{W - text_width(live, MONO, 17) - 15}" cy="314.5" r="4" fill="{c["signal"]}"/>')

    label = ("Maximilian Feix. Backend and infrastructure at a hosting company in Germany. "
             "Currently shipping proxy-scraper, spillage and RepoAtlas.")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="{escape(label)}">\n' + "\n".join(out) + "\n</svg>\n")


# ---------------------------------------------------------------- activity
# Same masthead treatment as the header: no background, four numbers, then the languages
# as bars in a single hue. Only public repositories are counted.

def render_activity(p: Profile, theme: str) -> str:
    c = THEMES[theme]
    W, H = 1200, 318
    out = []

    merged = sum(n for _, _, n in p.contrib)
    tiles = [(fmt_int(p.releases), "releases shipped"), (fmt_int(merged), "upstream PRs merged"),
             (fmt_int(len(p.contrib)), "projects contributed to"), (fmt_int(p.stars), "stars on my projects")]
    for i, (value, label) in enumerate(tiles):
        x = i * 300
        out.append(text(value, x - 2, 62, DISPLAY, 68, c["ink"], tracking=-2.4))
        out.append(text(label, x, 100, MONO, 17, c["muted"]))

    out.append(f'<rect y="134" width="{W}" height="1" fill="{c["rule"]}"/>')
    out.append(text("languages, by share of code in my public repositories", 0, 172, MONO, 17, c["faint"]))

    langs = p.languages[:6]
    top = langs[0][1] if langs else 1
    for i, (name, share) in enumerate(langs):
        x, y = (i // 3) * 640, 216 + (i % 3) * 40
        out.append(text(name, x, y, SANS, 21, c["ink"]))
        out.append(f'<rect x="{x + 150}" y="{y - 12}" width="320" height="8" rx="4" fill="{c["rule"]}"/>')
        out.append(f'<rect x="{x + 150}" y="{y - 12}" width="{max(8, round(320 * share / top))}" height="8" rx="4" '
                   f'fill="{c["signal"]}"/>')
        pct = f"{share:.1f}%" if share >= 1 else "<1%"
        out.append(text(pct, x + 560, y, MONO, 17, c["muted"], anchor="end"))

    label = (", ".join(f"{v} {l}" for v, l in tiles) + ". Languages: "
             + ", ".join(f"{n} {s:.0f}%" for n, s in langs) + ".")
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
    fit: bool = False  # letterbox instead of trimming, padded with the screenshot's own background


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
        Card(SPILLAGE, "spillage", "Python",
             "Finds the API keys your coding agents spilled into their logs.",
             [("13", True), (" agents, 0 dependencies", False), ("   ·   ", False),
              (p.spillage_release or "latest", False)],
             f"{raw}/{SPILLAGE}/main/docs/social-preview.png", (0, 0, 1, 1),
             dict(bg="#0E0F13", ink="#EAE5DA", muted="#9A988F", accent="#FF6B4A", rule="#26272D"), fit=True),
        Card(PREVIEW, "gha-preview", "TypeScript",
             "See a GitHub Actions run as a job graph before you push.",
             [("in the browser", True), (", nothing uploaded", False), ("   ·   ", False),
              (p.preview_release or "latest", False)],
             f"{raw}/{PREVIEW}/main/docs/assets/playground.png", (0, 0, 1, 0.42),
             dict(bg="#FAFAF7", ink="#17211A", muted="#5F6B62", accent="#2E6B43", rule="#DDE3DC")),
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
    if card.fit:
        img = img.crop(tuple(round(v) for v in box))
        scale = min(w / bw, h / bh)
        img = img.resize((round(bw * scale), round(bh * scale)), Image.LANCZOS)
        canvas = Image.new("RGB", (w, h), img.getpixel((0, 0)))
        canvas.paste(img, ((w - img.width) // 2, (h - img.height) // 2))
        img = canvas
    elif bw / bh > want:  # too wide: trim the sides evenly
        cut = (bw - bh * want) / 2
        box[0] += cut; box[2] -= cut
    else:  # too tall: keep the top
        box[3] = box[1] + bw / want
    if not card.fit:
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


def short(n: int) -> str:
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def render_contrib(p: Profile) -> str:
    if not p.contrib:
        return "_Nothing merged yet._"
    out = []
    for name, stars, n in p.contrib[:6]:
        prs = f"https://github.com/{name}/pulls?q=is%3Apr+is%3Amerged+author%3A{USER}"
        label = "merged PR" if n == 1 else "merged PRs"
        out.append(f"- **[{name}](https://github.com/{name})** <sub>★ {short(stars)}</sub><br>"
                   f"<sub>[{n} {label}]({prs})</sub>")
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
        (ROOT / "assets" / f"activity-{theme}.svg").write_text(render_activity(p, theme), encoding="utf-8")
    for card in cards(p):
        (ROOT / "assets" / f"card-{card.slug}.svg").write_text(render_card(card), encoding="utf-8")
    readme = ROOT / "README.md"
    body = replace_section(readme.read_text(encoding="utf-8"), "SHIPPED", render_shipped(p))
    readme.write_text(replace_section(body, "CONTRIB", render_contrib(p)), encoding="utf-8")
    print(f"repos={p.repos} stars={p.stars} followers={p.followers} release={p.release} "
          f"atlas={p.atlas_release} spillage={p.spillage_release} preview={p.preview_release} "
          f"live={p.live_proxies} shipped={len(p.shipped)} contrib={len(p.contrib)} releases={p.releases}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
