#!/usr/bin/env python3
"""Build the dynamic parts of the profile.

- assets/header-dark.svg / header-light.svg: banner with the latest releases of the four projects
- assets/card-<repo>.svg: featured project cards, a real screenshot plus a few facts
- assets/activity-dark.svg / activity-light.svg: releases, contributions, stars and languages
- data/metrics.json: the last valid value of every version and download figure, with source and fetch time
- data/downloads.csv: one dated row per successful download fetch, so growth can be shown later
- data/badges/*.json: Shields endpoint badges made from data/metrics.json
- README.md: badge rows, "Recent releases" and "About the numbers" between their markers

Only public data is used. Runs in GitHub Actions (see .github/workflows/profile.yml),
works locally too: `pip install -r scripts/requirements.txt`, then
`GITHUB_TOKEN=$(gh auth token) python3 scripts/build_profile.py`.

Rules for the numbers: a failed fetch never becomes 0 and never overwrites the last valid value,
which keeps the time it was fetched; download figures are fetched at most once per REFRESH.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

USER = "maximilianfeix"
SKIP_REPOS = {"community-content", USER}
# Accounts and organisations of my own (set as the repository variable PROFILE_EXCLUDE_OWNERS,
# comma-separated): pull requests there are not contributions to other people's projects.
OWN = {USER} | {o.strip().lower() for o in os.environ.get("EXCLUDE_OWNERS", "").split(",") if o.strip()}
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
METRICS = DATA / "metrics.json"
HISTORY = DATA / "downloads.csv"
BADGES = DATA / "badges"
REFRESH = timedelta(hours=20)  # npm and PyPI publish daily figures; no need to ask more often

STACK = ["TypeScript", "Node.js", "Python", "Go", "Linux"]


@dataclass
class Project:
    slug: str
    title: str
    channel: str  # npm | pypi | github
    package: str  # registry name, or a regex for the release files that are the program itself
    ci: str  # workflow file whose status the badge shows


# Package names checked against the registry metadata (repository link, provenance of the
# latest upload pointing to this repository's release workflow), not just by name.
PROJECTS = [
    Project("hexvero", "hexvero", "npm", "hexvero", "ci.yml"),
    Project("proxy-scraper", "proxy-scraper", "pypi", "proxy-scraper-cli", "tests.yml"),
    Project("spillage", "spillage", "pypi", "spillage", "tests.yml"),
    # the four GoReleaser archives per release; checksums.txt and anything else is left out
    Project("dockdu", "dockdu", "github", r"dockdu_\d+\.\d+\.\d+_(darwin|linux|windows)_(amd64|arm64)\.(tar\.gz|zip)",
            "ci.yml"),
]


class NoData(Exception):
    """The source answered, but has no figure for this package (yet)."""


def request(url: str, accept: str = "application/json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": f"{USER}-profile"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com"):
        req.add_header("Authorization", f"Bearer {token}")
    return urllib.request.urlopen(req, timeout=30)


def get(url: str):
    with request(url, "application/vnd.github+json") as resp:
        return json.load(resp)


def get_pages(url: str) -> list:
    """Every page of a GitHub list endpoint, following the Link header."""
    out = []
    while url:
        with request(url, "application/vnd.github+json") as resp:
            out.extend(json.load(resp))
            links = resp.headers.get("Link", "")
        url = next((part.split(";")[0].strip(" <>") for part in links.split(",") if 'rel="next"' in part), "")
    return out


def gql(query: str) -> dict:
    req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps({"query": query}).encode(),
                                 headers={"User-Agent": USER, "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["data"]


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# ---------------------------------------------------------------- versions and downloads

def fetch_version(pr: Project) -> dict:
    if pr.channel == "npm":
        with request(f"https://registry.npmjs.org/{pr.package}") as resp:
            v = json.load(resp)["dist-tags"]["latest"]
        return dict(value=v, source=f"registry.npmjs.org/{pr.package} (dist-tag latest)",
                    url=f"https://www.npmjs.com/package/{pr.package}")
    if pr.channel == "pypi":
        with request(f"https://pypi.org/pypi/{pr.package}/json") as resp:
            v = json.load(resp)["info"]["version"]
        return dict(value=v, source=f"pypi.org/pypi/{pr.package}/json", url=f"https://pypi.org/project/{pr.package}/")
    rel = get(f"https://api.github.com/repos/{USER}/{pr.slug}/releases/latest")
    return dict(value=rel["tag_name"].lstrip("v"), source=f"GitHub API, latest release of {USER}/{pr.slug}",
                url=rel["html_url"])


def fetch_downloads(pr: Project) -> dict:
    if pr.channel == "npm":
        # rolling window: the 30 days up to the last day npm has published figures for
        try:
            with request(f"https://api.npmjs.org/downloads/range/last-month/{pr.package}") as resp:
                d = json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NoData("npm has no download figures for this package yet") from None
            raise
        if "error" in d:
            raise NoData(d["error"])
        return dict(value=sum(x["downloads"] for x in d["downloads"]), start=d["start"], end=d["end"],
                    label="npm downloads", period="30 days",
                    definition="Sum of the daily npm downloads of the CLI package in the 30-day window npm "
                               "reports; the workspace packages it depends on are not added.",
                    source=f"api.npmjs.org/downloads/range/last-month/{pr.package}",
                    url=f"https://www.npmjs.com/package/{pr.package}")
    if pr.channel == "pypi":
        # pypistats' own "last_month" figure does not match any window (it reported 0 for a package with
        # 478 downloads that week), so the window is summed here from the daily figures.
        with request(f"https://pypistats.org/api/packages/{pr.package}/overall?mirrors=false") as resp:
            days = {x["date"]: x["downloads"] for x in json.load(resp)["data"] if x["category"] == "without_mirrors"}
        if not days:
            raise NoData("pypistats has no figures for this package yet")
        end = max(date.fromisoformat(d) for d in days)
        start = end - timedelta(days=29)
        total = sum(n for d, n in days.items() if start <= date.fromisoformat(d) <= end)
        first = min(date.fromisoformat(d) for d in days)
        younger = f" The package's figures start on {first.isoformat()}." if first > start else ""
        return dict(value=total, start=start.isoformat(), end=end.isoformat(), label="PyPI downloads",
                    period="30 days",
                    definition="Sum of the daily PyPI downloads without mirrors (pypistats.org, from PyPI's "
                               "public BigQuery data) over the 30 days up to the last day with figures." + younger,
                    source=f"pypistats.org/api/packages/{pr.package}/overall?mirrors=false",
                    url=f"https://pypistats.org/packages/{pr.package}")
    pattern = re.compile(pr.package)
    total, files, releases = 0, 0, get_pages(f"https://api.github.com/repos/{USER}/{pr.slug}/releases?per_page=100")
    for rel in releases:
        if rel["draft"]:
            continue
        for asset in get_pages(f"https://api.github.com/repos/{USER}/{pr.slug}/releases/{rel['id']}/assets?per_page=100"):
            if pattern.fullmatch(asset["name"]):
                total += asset["download_count"]
                files += 1
    if not files:
        raise NoData("no release files match the program-file pattern")
    return dict(value=total, start=None, end=None, label="GitHub downloads", period="all time",
                definition=f"Sum of download_count of the {files} program archives (one per OS and CPU) across "
                           f"all {len(releases)} releases; checksums and other files are not counted. "
                           "Homebrew cask installs fetch these archives and are included; go install, "
                           "container image pulls and git clones are not.",
                source=f"GitHub API, releases and assets of {USER}/{pr.slug} (all pages)",
                url=f"https://github.com/{USER}/{pr.slug}/releases")


def load_metrics() -> dict:
    try:
        return json.loads(METRICS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def update_metrics(now: datetime, log: list) -> dict:
    """Refresh what is due. On failure the last valid entry stays as it is, with its own fetch time."""
    m = load_metrics()
    for pr in PROJECTS:
        for kind, fetch in (("version", fetch_version), ("downloads", fetch_downloads)):
            key = f"{pr.slug}/{kind}"
            old = m.get(key, {})
            if kind == "downloads" and old.get("status") == "ok" and now - parse(old["fetched_at"]) < REFRESH:
                continue  # fresh enough; a failed or empty fetch is retried on the next run
            try:
                new = fetch(pr)
            except NoData as e:
                old.update(last_attempt=iso(now), status=f"no data: {e}")
                m[key] = old
                log.append(f"{key}: no data ({e})")
                continue
            except Exception as e:  # network, rate limit, changed format: keep the last valid value
                old.update(last_attempt=iso(now), status=f"fetch failed: {type(e).__name__}")
                m[key] = old
                log.append(f"{key}: fetch failed ({type(e).__name__}: {str(e)[:120]})")
                continue
            m[key] = {**new, "fetched_at": iso(now), "last_attempt": iso(now), "status": "ok"}
            if kind == "downloads":
                append_history(now, pr, m[key])
    METRICS.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return m


def append_history(now: datetime, pr: Project, d: dict) -> None:
    new = not HISTORY.exists()
    with HISTORY.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["fetched_at", "project", "source", "package", "period", "window_start", "window_end", "value"])
        w.writerow([iso(now), pr.slug, pr.channel, pr.package if pr.channel != "github" else f"{USER}/{pr.slug}",
                    d["period"], d["start"] or "", d["end"] or "", d["value"]])


def valid(m: dict, key: str) -> dict | None:
    e = m.get(key)
    return e if e and "value" in e else None


def short(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


BADGE_LABEL, BADGE_VALUE = "#30363D", "#57606A"  # neutral in both themes


def write_badges(m: dict) -> None:
    BADGES.mkdir(parents=True, exist_ok=True)
    for pr in PROJECTS:
        for kind in ("version", "downloads"):
            path = BADGES / f"{pr.slug}-{kind}.json"
            e = valid(m, f"{pr.slug}/{kind}")
            if not e:
                path.unlink(missing_ok=True)  # no figure yet: no badge, rather than a misleading one
                continue
            if kind == "version":
                label = {"npm": "npm", "pypi": "PyPI", "github": "release"}[pr.channel]
                message = f"v{e['value']}"
            else:
                label, message = e["label"], f"{short(e['value'])} / {e['period']}"
            path.write_text(json.dumps(dict(schemaVersion=1, label=label, message=message, color=BADGE_VALUE,
                                            labelColor=BADGE_LABEL, cacheSeconds=3600)) + "\n", encoding="utf-8")


def render_badges(m: dict, pr: Project) -> str:
    raw = f"https://raw.githubusercontent.com/{USER}/{USER}/main/data/badges"
    style = "style=flat-square"
    out = []
    for kind, alt in (("version", "latest version"), ("downloads", "downloads")):
        e = valid(m, f"{pr.slug}/{kind}")
        if e:
            src = f"https://img.shields.io/endpoint?url={urllib.parse.quote(f'{raw}/{pr.slug}-{kind}.json', safe='')}&{style}"
            out.append(f'<a href="{e["url"]}"><img src="{src}" alt="{alt}"></a>')
    wf = f"https://github.com/{USER}/{pr.slug}/actions/workflows/{pr.ci}"
    src = (f"https://img.shields.io/github/actions/workflow/status/{USER}/{pr.slug}/{pr.ci}?branch=main&label=CI"
           f"&{style}&labelColor={BADGE_LABEL[1:]}")
    out.append(f'<a href="{wf}"><img src="{src}" alt="CI status on main"></a>')
    return "<p>" + " ".join(out) + "</p>"


def fmt_day(ts: str) -> str:
    return parse(ts).strftime("%-d %b %Y")


def render_data(m: dict) -> str:
    rows = ["| Figure | Value | Window | Definition | Source | Fetched |", "|---|---|---|---|---|---|"]
    missing = []
    for pr in PROJECTS:
        e = valid(m, f"{pr.slug}/downloads")
        status = m.get(f"{pr.slug}/downloads", {}).get("status", "")
        if not e:
            missing.append(f"**{pr.title}**: {status or 'not fetched yet'}")
            continue
        window = f"{e['start']} – {e['end']}" if e["start"] else "all time"
        stale = "" if status == "ok" else f" (last attempt: {status})"
        rows.append(f"| {pr.title} · {e['label']} | {e['value']:,} | {window} | {e['definition'].replace('|', '/')} | "
                    f"[{e['source']}]({e['url']}) | {fmt_day(e['fetched_at'])}{stale} |")
    out = "\n".join(rows)
    if missing:
        out += "\n\nNo figure shown for " + "; ".join(missing) + "."
    return out


# ---------------------------------------------------------------- activity and releases

@dataclass
class Profile:
    stars: int = 0
    code_prs: int = 0  # merged in other people's projects, list entries left out
    list_prs: int = 0  # entries for my projects in "awesome" lists
    code_repos: int = 0
    releases: int = 0
    languages: list = field(default_factory=list)  # (name, share of bytes in percent), largest first
    shipped: list = field(default_factory=list)
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def collect() -> Profile:
    p = Profile()
    repos = [r for r in get_pages(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
             if not r["fork"] and not r["private"] and r["name"] not in SKIP_REPOS]
    p.stars = sum(r["stargazers_count"] for r in repos)

    items = []
    for r in repos:
        for rel in get(f"https://api.github.com/repos/{USER}/{r['name']}/releases?per_page=5"):
            if not rel["draft"] and not rel["prerelease"]:
                items.append((rel["published_at"], r["name"], rel["tag_name"], rel["html_url"]))
    items.sort(reverse=True)
    per_repo: dict = {}
    for item in items:  # the newest release per repo, so one busy project doesn't fill the list
        per_repo[item[1]] = per_repo.get(item[1], 0) + 1
        if per_repo[item[1]] == 1 and len(p.shipped) < 5:
            p.shipped.append(item)

    # merged pull requests in other people's public projects
    code_repos = set()
    query = f"is:pr+is:merged+author:{USER}+-user:{USER}"
    for page in range(1, 11):  # the search API stops at 1,000 results
        found = get(f"https://api.github.com/search/issues?q={query}&per_page=100&page={page}")["items"]
        for pr in found:
            name = pr["repository_url"].split("/repos/", 1)[1]
            if name.split("/")[0].lower() in OWN:
                continue
            if "awesome" in name.split("/")[1].lower():
                p.list_prs += 1
            else:
                p.code_prs += 1
                code_repos.add(name)
        if len(found) < 100:
            break
    p.code_repos = len(code_repos)

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


# ---------------------------------------------------------------- header

THEMES = {
    # text colours on GitHub's own page colour; the banner adds its SURFACE on top
    "light": dict(ink="#121113", muted="#57564F", faint="#7E7D77", rule="#D0D7DE", signal="#3F5A00"),
    "dark": dict(ink="#EDEBE6", muted="#A6A59F", faint="#7D7C77", rule="#30363D", signal="#D4F77A"),
}
DISPLAY, SANS, SANS_B = "Geist-SemiBold", "Geist-Regular", "Geist-SemiBold"
MONO = "GeistMono-Regular"


def fmt_int(n: int) -> str:
    return f"{n:,}"


# the banner is a card of its own, like the project cards below it
SURFACE = {
    "light": dict(bg="#F4F3EE", panel="#FFFFFF", line="#DEDCD4", dot="#CFCDC4", glow="#B9E34F", glow_a=0.42),
    "dark": dict(bg="#0E0E10", panel="#16161A", line="#2A2A2F", dot="#34343A", glow="#C6F36B", glow_a=0.17),
}
POSITIONING = "Backend and infrastructure at a hosting company in Germany."


def render_header(p: Profile, m: dict, theme: str) -> str:
    c = {**THEMES[theme], **SURFACE[theme]}
    W, H, PAD = 1200, 400, 56
    out = []

    out.append(f"""<defs>
<clipPath id="card"><rect width="{W}" height="{H}" rx="20"/></clipPath>
<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.2" fill="{c["dot"]}"/></pattern>
<linearGradient id="fade" x1="0" x2="1" y1="0" y2="0"><stop offset=".3" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff"/></linearGradient>
<mask id="right"><rect width="{W}" height="{H}" fill="url(#fade)"/></mask>
<radialGradient id="glow" cx="{W - 190}" cy="-40" r="560" gradientUnits="userSpaceOnUse"><stop stop-color="{c["glow"]}" stop-opacity="{c["glow_a"]}"/><stop offset="1" stop-color="{c["glow"]}" stop-opacity="0"/></radialGradient>
</defs>
<g clip-path="url(#card)">
<rect width="{W}" height="{H}" fill="{c["bg"]}"/>
<rect width="{W}" height="{H}" fill="url(#dots)" mask="url(#right)"/>
<rect width="{W}" height="{H}" fill="url(#glow)"/>""")

    # left: what I do, who I am, what I build
    out.append(f'<rect x="{PAD}" y="70" width="28" height="3" rx="1.5" fill="{c["signal"]}"/>')
    out.append(text("BACKEND  /  INFRASTRUCTURE  /  DEVELOPER TOOLS", PAD + 42, 77, MONO, 15, c["muted"], tracking=1.6))

    name, size, track = "Maximilian Feix", 100, -4.2
    out.append(text(name, PAD - 4, 186, DISPLAY, size, c["ink"], tracking=track))
    out.append(text(".", PAD - 4 + text_width(name, DISPLAY, size, track) + 1, 186, DISPLAY, size, c["signal"]))

    out.append(text(POSITIONING, PAD, 240, SANS, 23, c["muted"]))
    out.append(text("Developer tools that show their evidence.", PAD, 274, SANS, 23, c["muted"]))

    x = PAD
    for tech in STACK:  # the stack as quiet chips along the bottom edge
        w = text_width(tech, MONO, 15) + 28
        out.append(f'<rect x="{x}" y="314" width="{w:.1f}" height="32" rx="16" fill="none" stroke="{c["line"]}"/>')
        out.append(text(tech, x + 14, 335.5, MONO, 15, c["muted"]))
        x += w + 10

    # right: the latest version of each featured project, as the registries report it
    px, py, pw, ph = 800, PAD, W - PAD - 800, H - 2 * PAD
    out.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="14" fill="{c["panel"]}" stroke="{c["line"]}"/>')
    out.append(f'<circle cx="{px + 27}" cy="{py + 30}" r="4.5" fill="{c["signal"]}"/>')
    out.append(text("LATEST RELEASES", px + 42, py + 35, MONO, 14, c["ink"], tracking=1.4))
    out.append(f'<rect x="{px}" y="{py + 58}" width="{pw}" height="1" fill="{c["line"]}"/>')
    rows = [(pr.title, valid(m, f"{pr.slug}/version")) for pr in PROJECTS]
    rows = [(t, e) for t, e in rows if e]  # a project without a known version gets no row
    for i, (title, e) in enumerate(rows):
        y = py + 104 + i * 44
        out.append(text(title, px + 22, y, SANS, 19, c["ink"]))
        out.append(text(f"v{e['value']}", px + pw - 22, y, MONO, 16, c["muted"], anchor="end"))
    out.append(text(f"as of {p.now.strftime('%-d %b %Y')}", px + 22, py + ph - 22, MONO, 13, c["faint"]))

    out.append(f'</g>\n<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="none" stroke="{c["line"]}"/>')

    label = (f"Maximilian Feix. {POSITIONING} Developer tools that show their evidence. Latest releases: "
             + ", ".join(f"{t} v{e['value']}" for t, e in rows) + ".")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="{escape(label)}">\n' + "\n".join(out) + "\n</svg>\n")


# ---------------------------------------------------------------- activity
# Same masthead treatment as the header: no background, four numbers, then the languages
# as bars in a single hue. Only public repositories are counted.

def render_activity(p: Profile, theme: str) -> str:
    c = THEMES[theme]
    W, H = 1200, 318
    out = []

    tiles = [(fmt_int(p.releases), "releases on GitHub"), (fmt_int(p.code_prs), "PRs merged upstream"),
             (fmt_int(p.code_repos), "projects patched"), (fmt_int(p.stars), "stars on my repos")]
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


def cards(m: dict) -> list[Card]:
    raw = f"https://raw.githubusercontent.com/{USER}"

    def version(slug: str) -> list:
        e = valid(m, f"{slug}/version")
        return [("   ·   ", False), (f"v{e['value']}", False)] if e else []

    return [
        Card("hexvero", "hexvero", "TypeScript",
             "Static analysis of binaries and app bundles, every fact with its source.",
             [("npx hexvero", True), (" · CLI, MCP server, web UI", False)] + version("hexvero"),
             f"{raw}/hexvero/main/docs/screenshots/ui-overview.png", (0.185, 0.06, 0.70, 0.62),
             dict(bg="#1B1D21", ink="#ECEAE4", muted="#9C9A94", accent="#F2B84B", rule="#2C2F35")),
        Card("proxy-scraper", "proxy-scraper", "Python",
             "Public proxies from 700+ sources, kept only if they pass every check.",
             [("hourly", True), (" list · rotating proxy · MCP", False)] + version("proxy-scraper"),
             f"{raw}/proxy-scraper/main/docs/website.png", (0.055, 0.17, 0.96, 0.785),
             dict(bg="#141416", ink="#EDEBE4", muted="#9C9B96", accent="#C6F36B", rule="#2A2A2E")),
        Card("spillage", "spillage", "Python",
             "Keeps API keys out of coding agents and finds the ones that leaked.",
             [("0", True), (" dependencies, no network", False)] + version("spillage"),
             f"{raw}/spillage/main/docs/social-preview.png", (0, 0, 1, 1),
             dict(bg="#0E0F13", ink="#EAE5DA", muted="#9A988F", accent="#FF6B4A", rule="#26272D"), fit=True),
        Card("dockdu", "dockdu", "Go",
             "Where Docker's disk space went, and what prune won't give back.",
             [("read-only", True), (", one command", False)] + version("dockdu"),
             f"{raw}/dockdu/main/docs/demo.png", (0, 0, 0.5, 0.425),
             dict(bg="#141E27", ink="#E6EEF2", muted="#8FA1AD", accent="#36B6C5", rule="#22323F")),
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
        facts.append(text(s, x, y + 150, MONO, 19, c["accent"] if strong else c["muted"]))
        x += text_width(s, MONO, 19)
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
        return "_No releases yet._"
    return "\n".join(f"- **[{repo} {tag}]({url})** <sub>· {fmt_day(when)}</sub>" for when, repo, tag, url in p.shipped)


def render_numbers_note(p: Profile, m: dict) -> str:
    fetched = [parse(e["fetched_at"]) for k, e in m.items() if k.endswith("/downloads") and "value" in e]
    since = f"downloads fetched {max(fetched).strftime('%-d %b %Y')}" if fetched else "no download figures yet"
    return (f"<sub>Figures as of {p.now.strftime('%-d %b %Y')} ({since}), updated regularly by this repository's workflow. "
            f"Upstream counts leave out my own accounts and {p.list_prs} entries for my projects in awesome lists. "
            "Downloads are downloads, not users or unique installs.</sub>")


def replace_section(text: str, name: str, body: str) -> str:
    pattern = re.compile(rf"(<!--{re.escape(name)}:start-->).*?(<!--{re.escape(name)}:end-->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"marker {name} missing in README.md")
    return pattern.sub(lambda mt: f"{mt.group(1)}\n{body}\n{mt.group(2)}", text)


def main() -> int:
    DATA.mkdir(exist_ok=True)
    p = collect()
    log: list = []
    m = update_metrics(p.now, log)
    write_badges(m)
    for theme in THEMES:
        (ROOT / "assets" / f"header-{theme}.svg").write_text(render_header(p, m, theme), encoding="utf-8")
        (ROOT / "assets" / f"activity-{theme}.svg").write_text(render_activity(p, theme), encoding="utf-8")
    for card in cards(m):
        (ROOT / "assets" / f"card-{card.slug}.svg").write_text(render_card(card), encoding="utf-8")

    readme = ROOT / "README.md"
    body = readme.read_text(encoding="utf-8")
    for pr in PROJECTS:
        body = replace_section(body, f"BADGES:{pr.slug}", render_badges(m, pr))
    body = replace_section(body, "SHIPPED", render_shipped(p))
    body = replace_section(body, "NUMBERS", render_numbers_note(p, m))
    body = replace_section(body, "DATA", render_data(m))
    readme.write_text(body, encoding="utf-8")

    print(f"stars={p.stars} releases={p.releases} code_prs={p.code_prs} code_repos={p.code_repos} "
          f"list_prs={p.list_prs} shipped={len(p.shipped)}")
    for key in sorted(m):
        e = m[key]
        print(f"- {key}: {e.get('value', '—')} ({e.get('status')}, fetched {e.get('fetched_at', 'never')})")
    for line in log:
        print(f"- {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
