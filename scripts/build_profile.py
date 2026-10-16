#!/usr/bin/env python3
"""Build the dynamic parts of the profile.

- assets/stats-dark.svg / stats-light.svg: four numbers about my public work
- assets/snake/contributions-static-{light,dark}.svg: the contribution grid without animation,
  shown instead of the snake when the viewer asks for reduced motion
- data/metrics.json: the last valid value of every version and download figure, with source and fetch time
- data/downloads.csv: one dated row per successful download fetch, so growth can be shown later
- data/badges/*.json: Shields endpoint badges made from data/metrics.json
- README.md: badge rows, "Recently shipped" and the notes on the numbers, between their markers

The snake itself comes from .github/workflows/snake.yml (Platane/snk).

Only public data is used. Runs in GitHub Actions (see .github/workflows/profile.yml),
works locally too: `pip install -r scripts/requirements.txt`, then
`GITHUB_TOKEN=$(gh auth token) EXCLUDE_OWNERS=… python3 scripts/build_profile.py`.

Rules for the numbers: a failed fetch never becomes 0 and never overwrites the last valid value,
which keeps the time it was fetched; download figures are fetched at most once per REFRESH.
Anything else that fails stops the run, so the files from the last good run stay in place.
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
SNAKE = ROOT / "assets" / "snake"
REFRESH = timedelta(hours=20)  # npm and PyPI publish daily figures; no need to ask more often
# Releases from these repositories can appear under "Recently shipped"
SHIPPED_FROM = ["hexvero", "proxy-scraper", "spillage", "dockdu", "repoville", "kuerzel", "repoatlas"]


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
        body = json.load(resp)
    if body.get("errors"):  # GraphQL answers 200 with partial data; partial data must not become a number
        raise RuntimeError("GraphQL errors: " + "; ".join(e.get("message", "?") for e in body["errors"]))
    return body["data"]


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def fmt_day(ts: str) -> str:
    return parse(ts).strftime("%-d %b %Y")


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
    return " ".join(out)


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
    prs: int = 0  # merged in other people's public repositories, list entries left out
    list_prs: int = 0  # entries for my own projects in "awesome" lists
    repos: int = 0  # distinct other people's public repositories with such a PR
    releases_year: int = 0  # published (non-draft) releases of my public repositories in the last 365 days
    search_complete: bool = True
    grid: list = field(default_factory=list)  # weeks of (date, level 0..4)
    shipped: list = field(default_factory=list)
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def collect() -> Profile:
    p = Profile()
    repos = [r for r in get_pages(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
             if not r["fork"] and not r["private"] and r["name"] not in SKIP_REPOS]
    p.stars = sum(r["stargazers_count"] for r in repos)

    year_ago = p.now - timedelta(days=365)
    latest: dict = {}
    for r in repos:
        seen = set()
        for rel in get_pages(f"https://api.github.com/repos/{USER}/{r['name']}/releases?per_page=100"):
            if rel["draft"] or rel["id"] in seen or not rel["published_at"]:
                continue
            seen.add(rel["id"])
            if parse(rel["published_at"]) >= year_ago:
                p.releases_year += 1
            if r["name"] in SHIPPED_FROM and not rel["prerelease"]:
                if r["name"] not in latest or rel["published_at"] > latest[r["name"]][0]:
                    latest[r["name"]] = (rel["published_at"], r["name"], rel["tag_name"], rel["html_url"])
    p.shipped = sorted(latest.values(), reverse=True)[:3]  # the newest release of the three latest projects

    # merged pull requests in other people's public repositories
    seen_prs: set = set()
    per_repo: dict = {}
    query = f"is:pr+is:merged+author:{USER}+-user:{USER}"
    for page in range(1, 11):  # the search API stops at 1,000 results
        res = get(f"https://api.github.com/search/issues?q={query}&per_page=100&page={page}")
        if res.get("incomplete_results"):
            p.search_complete = False
        for pr in res["items"]:
            name = pr["repository_url"].split("/repos/", 1)[1]
            if name.split("/")[0].lower() in OWN or pr["html_url"] in seen_prs:
                continue
            seen_prs.add(pr["html_url"])
            per_repo.setdefault(name, []).append(pr)
        if len(res["items"]) < 100:
            break
    if res["total_count"] > 1000:
        p.search_complete = False
    for name, prs in per_repo.items():
        try:
            repo = get(f"https://api.github.com/repos/{name}")
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):  # not visible to this token, so not public
                continue
            raise
        if repo["private"] or repo.get("visibility", "public") != "public":
            continue  # a token can see private repositories; they never count here
        if "awesome" in repo["name"].lower():
            p.list_prs += len(prs)
            continue
        p.prs += len(prs)
        p.repos += 1

    cal = gql(f'''{{ user(login: "{USER}") {{ contributionsCollection {{ contributionCalendar {{
        weeks {{ contributionDays {{ date weekday contributionLevel }} }} }} }} }} }}''')
    for week in cal["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
        p.grid.append([(d["date"], d["weekday"], LEVELS[d["contributionLevel"]]) for d in week["contributionDays"]])
    if not p.grid:
        raise RuntimeError("empty contribution calendar")
    return p


# ---------------------------------------------------------------- typesetting
# Text is shaped with HarfBuzz and written out as outlines, so the panel looks the
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


# ---------------------------------------------------------------- stats panel and static grid

# One accent: the lime of the contribution levels. Text in GitHub's own ink colours.
THEMES = {
    "light": dict(ink="#1F2328", muted="#59636E", rule="#D1D9E0", accent="#3F5A0E"),
    "dark": dict(ink="#F0F6FC", muted="#9198A1", rule="#3D444D", accent="#C6F36B"),
}
# Same five colours as the snake (.github/workflows/snake.yml): no contributions, then four levels
GRID = {
    "light": ["#EBEDF0", "#CDE88A", "#9FCB45", "#6E9424", "#3F5A0E"],
    "dark": ["#151B23", "#2E4A12", "#4F7A1C", "#86B832", "#C6F36B"],
}
DISPLAY, MONO = "Geist-SemiBold", "GeistMono-Regular"


def fmt_int(n: int) -> str:
    return f"{n:,}"


def tiles(p: Profile) -> list[tuple[str, str]]:
    return [(fmt_int(p.stars), "stars on my repos"),
            (fmt_int(p.prs), "PRs merged elsewhere"),
            (fmt_int(p.repos), "projects patched"),
            (fmt_int(p.releases_year), "releases in 12 months")]


def render_stats(p: Profile, theme: str, cols: int = 4) -> str:
    """One row of four on wide screens; two rows of two for phones (assets/stats-*-narrow.svg)."""
    c = THEMES[theme]
    cell_w, cell_h = 300, 150
    W, H = cell_w * cols, 132 + cell_h * (4 // cols - 1)
    out = []
    for i, (value, label) in enumerate(tiles(p)):
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        if i % cols:
            out.append(f'<rect x="{x - 24}" y="{y + 14}" width="1" height="104" fill="{c["rule"]}"/>')
        out.append(text(value, x - 2, y + 70, DISPLAY, 64, c["ink"], tracking=-2.2))
        out.append(f'<rect x="{x}" y="{y + 90}" width="22" height="3" rx="1.5" fill="{c["accent"]}"/>')
        out.append(text(label, x, y + 122, MONO, 19, c["muted"]))
    label = ", ".join(f"{v} {l}" for v, l in tiles(p)) + "."
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="{escape(label)}">\n' + "\n".join(out) + "\n</svg>\n")


def render_grid(p: Profile, theme: str) -> str:
    """The contribution grid in the snake's geometry (16 px pitch, 12 px cells), without motion."""
    colors = GRID[theme]
    out = []
    for x, week in enumerate(p.grid):
        for day, weekday, level in week:
            out.append(f'<rect x="{x * 16 + 2}" y="{weekday * 16 + 2}" width="12" height="12" rx="2" '
                       f'fill="{colors[level]}"><title>{day}</title></rect>')
    days = sum(len(w) for w in p.grid)
    label = f"My GitHub contribution graph for the last {days} days, without animation."
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-16 -32 880 192" width="880" height="192" '
            f'role="img" aria-label="{escape(label)}">\n' + "\n".join(out) + "\n</svg>\n")


def render_snake() -> str:
    """The snake only once the snake workflow has produced it; until then the static grid alone."""
    static = ('<source media="(prefers-reduced-motion: reduce) and (prefers-color-scheme: dark)" '
              'srcset="./assets/snake/contributions-static-dark.svg">\n'
              '  <source media="(prefers-reduced-motion: reduce)" srcset="./assets/snake/contributions-static-light.svg">')
    if all((SNAKE / f).is_file() and (SNAKE / f).stat().st_size > 1000 for f in ("github-snake.svg", "github-snake-dark.svg")):
        return (f"<picture>\n  {static}\n"
                '  <source media="(prefers-color-scheme: dark)" srcset="./assets/snake/github-snake-dark.svg">\n'
                '  <img src="./assets/snake/github-snake.svg" alt="Animation of my GitHub contribution graph from the '
                'last year: a snake moves across the grid and eats the days with contributions." width="100%">\n'
                "</picture>\n\n<sub>My contribution graph as an animated snake, redrawn daily with "
                "[Platane/snk](https://github.com/Platane/snk). It's an animation, not a game you can play here.</sub>")
    return ("<picture>\n"
            '  <source media="(prefers-color-scheme: dark)" srcset="./assets/snake/contributions-static-dark.svg">\n'
            '  <img src="./assets/snake/contributions-static-light.svg" alt="My GitHub contribution graph from the last year" width="100%">\n'
            "</picture>")


def render_shipped(p: Profile) -> str:
    if not p.shipped:
        return "_No releases yet._"
    return "\n".join(f"- **[{repo} {tag}]({url})** <sub>· {fmt_day(when)}</sub>" for when, repo, tag, url in p.shipped)


def render_numbers_note(p: Profile, m: dict) -> str:
    fetched = [parse(e["fetched_at"]) for k, e in m.items() if k.endswith("/downloads") and "value" in e]
    since = f"downloads fetched {max(fetched).strftime('%-d %b %Y')}" if fetched else "no download figures yet"
    partial = "" if p.search_complete else " The PR search reported incomplete results, so the PR numbers are a lower bound."
    return (f"<sub>As of {p.now.strftime('%-d %b %Y')} ({since}), updated regularly by this repository's workflows. "
            "Public repositories only. PRs count merged pull requests in repositories I don't own; "
            f"{p.list_prs} entries for my own projects in awesome lists are left out. "
            f"Downloads are downloads, not users or unique installs.{partial}</sub>")


def replace_section(text: str, name: str, body: str) -> str:
    pattern = re.compile(rf"(<!--{re.escape(name)}:start-->).*?(<!--{re.escape(name)}:end-->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"marker {name} missing in README.md")
    return pattern.sub(lambda mt: f"{mt.group(1)}\n{body}\n{mt.group(2)}", text)


def main() -> int:
    DATA.mkdir(exist_ok=True)
    SNAKE.mkdir(parents=True, exist_ok=True)
    p = collect()
    log: list = []
    m = update_metrics(p.now, log)
    write_badges(m)
    for theme in THEMES:
        (ROOT / "assets" / f"stats-{theme}.svg").write_text(render_stats(p, theme), encoding="utf-8")
        (ROOT / "assets" / f"stats-{theme}-narrow.svg").write_text(render_stats(p, theme, cols=2), encoding="utf-8")
        (SNAKE / f"contributions-static-{theme}.svg").write_text(render_grid(p, theme), encoding="utf-8")

    readme = ROOT / "README.md"
    body = readme.read_text(encoding="utf-8")
    for pr in PROJECTS:
        body = replace_section(body, f"BADGES:{pr.slug}", render_badges(m, pr))
    body = replace_section(body, "SHIPPED", render_shipped(p))
    body = replace_section(body, "SNAKE", render_snake())
    body = replace_section(body, "NUMBERS", render_numbers_note(p, m))
    body = replace_section(body, "DATA", render_data(m))
    readme.write_text(body, encoding="utf-8")

    print(f"stars={p.stars} prs={p.prs} repos={p.repos} list_prs={p.list_prs} releases_12m={p.releases_year} "
          f"search_complete={p.search_complete} weeks={len(p.grid)} shipped={[s[1] + ' ' + s[2] for s in p.shipped]}")
    for key in sorted(m):
        e = m[key]
        print(f"- {key}: {e.get('value', '—')} ({e.get('status')}, fetched {e.get('fetched_at', 'never')})")
    for line in log:
        print(f"- {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
