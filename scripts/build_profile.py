#!/usr/bin/env python3
"""Build the dynamic parts of the profile.

- assets/header-dark.svg / header-light.svg: banner with a live status panel
- README.md: the "Recently shipped" list between the SHIPPED markers

Only public data is used. Runs in GitHub Actions (see .github/workflows/profile.yml),
works locally too: `GITHUB_TOKEN=$(gh auth token) python3 scripts/build_profile.py`.
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
SKIP_REPOS = {"community-content", USER}
ROOT = Path(__file__).resolve().parent.parent

BUILDING = "devprofile.dev"
LEARNING = "microservices"
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

    try:
        p.release = get(f"https://api.github.com/repos/{USER}/{FEATURED}/releases/latest")["tag_name"]
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


THEMES = {
    "dark": dict(bg1="#0B1622", bg2="#0F2233", grid="#16293B", glow="#38BDF8", text="#E6EDF3", muted="#8BA3B8",
                 faint="#5E7B94", accent="#38BDF8", green="#34D399", amber="#FBBF24", panel="#0D1B2A",
                 panel_top="#132638", border="#24405A", chip="#132638"),
    "light": dict(bg1="#F6F9FC", bg2="#EAF2F8", grid="#DCE7F0", glow="#0284C7", text="#10243A", muted="#43647E",
                  faint="#6B879E", accent="#0284C7", green="#10B981", amber="#B45309", panel="#FFFFFF",
                  panel_top="#F1F6FA", border="#D3E1EC", chip="#FFFFFF"),
}


def fmt_int(n: int) -> str:
    return f"{n:,}"


def render_header(p: Profile, theme: str) -> str:
    c = THEMES[theme]
    mono = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    sans = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

    # status panel lines: (label, value, value color)
    lines = [
        ("building", BUILDING, c["text"]),
        ("learning", LEARNING, c["text"]),
        ("shipping", f"{FEATURED} {p.release}".strip(), c["accent"]),
    ]
    if p.live_proxies:
        lines.append(("live list", f"{p.live_proxies} verified proxies", c["green"]))
    stats = [f"{p.repos} public repos", f"{p.followers} followers"]
    if p.stars >= 25:  # small numbers look odd in a banner
        stats.insert(1, f"{fmt_int(p.stars)} stars")
    lines.append(("github", " · ".join(stats), c["text"]))

    px, py, pw = 690, 44, 450
    ph = 84 + 30 * len(lines) + 20
    rows = []
    for i, (label, value, color) in enumerate(lines):
        y = py + 108 + 30 * i
        rows.append(
            f'<g class="line" style="animation-delay:{0.35 + 0.18 * (i + 1):.2f}s">'
            f'<text x="{px + 28}" y="{y}" fill="{c["faint"]}" font-family="{mono}" font-size="15">{escape(label)}</text>'
            f'<text x="{px + 140}" y="{y}" fill="{color}" font-family="{mono}" font-size="15">{escape(value)}</text></g>'
        )
    cursor_y = py + 108 + 30 * len(lines)

    chips, x = [], 64
    for name in STACK:
        w = 18 + 8.2 * len(name)
        chips.append(
            f'<g class="chip" style="animation-delay:{0.25 + 0.08 * len(chips):.2f}s">'
            f'<rect x="{x}" y="226" width="{w:.0f}" height="30" rx="15" fill="{c["chip"]}" stroke="{c["border"]}"/>'
            f'<text x="{x + w / 2:.0f}" y="246" text-anchor="middle" fill="{c["muted"]}" font-family="{mono}" '
            f'font-size="13">{escape(name)}</text></g>'
        )
        x += w + 10

    updated = p.now.strftime("%d %b %Y")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 320" width="1200" height="320" role="img" aria-label="Maximilian Feix — backend, infrastructure, automation. Building {BUILDING}, learning {LEARNING}, shipping {FEATURED}.">
  <style>
    .line, .chip, .fade {{ animation: fade .6s ease-out both; }}
    .pulse {{ animation: pulse 2.4s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }}
    .cursor {{ animation: blink 1.1s steps(1) infinite; }}
    .scan {{ animation: scan 6s linear infinite; }}
    @keyframes fade {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; transform: scale(1); }} 50% {{ opacity: .35; transform: scale(1.8); }} }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    @keyframes scan {{ from {{ transform: translateX(-300px); }} to {{ transform: translateX(1500px); }} }}
    @media (prefers-reduced-motion: reduce) {{ .line, .chip, .fade, .pulse, .cursor, .scan {{ animation: none; }} }}
  </style>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{c["bg1"]}"/><stop offset="1" stop-color="{c["bg2"]}"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.78" cy="0.2" r="0.6">
      <stop offset="0" stop-color="{c["glow"]}" stop-opacity=".16"/><stop offset="1" stop-color="{c["glow"]}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="beam" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{c["accent"]}" stop-opacity="0"/><stop offset=".5" stop-color="{c["accent"]}" stop-opacity=".9"/><stop offset="1" stop-color="{c["accent"]}" stop-opacity="0"/>
    </linearGradient>
    <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M32 0H0V32" fill="none" stroke="{c["grid"]}" stroke-width="1"/>
    </pattern>
    <clipPath id="frame"><rect width="1200" height="320" rx="18"/></clipPath>
  </defs>
  <g clip-path="url(#frame)">
    <rect width="1200" height="320" fill="url(#bg)"/>
    <rect width="1200" height="320" fill="url(#grid)" opacity=".55"/>
    <rect width="1200" height="320" fill="url(#glow)"/>
    <rect class="scan" y="317" width="300" height="3" fill="url(#beam)"/>
  </g>

  <g class="fade">
    <text x="64" y="84" fill="{c["accent"]}" font-family="{mono}" font-size="14" letter-spacing="3">BACKEND · INFRASTRUCTURE · AUTOMATION</text>
    <text x="62" y="148" fill="{c["text"]}" font-family="{sans}" font-size="58" font-weight="800" letter-spacing="-1.5">Maximilian Feix</text>
    <rect x="64" y="166" width="72" height="4" rx="2" fill="{c["accent"]}"/>
    <text x="64" y="204" fill="{c["muted"]}" font-family="{sans}" font-size="19">building and keeping things online, from Germany</text>
  </g>
  {"".join(chips)}

  <g class="fade" style="animation-delay:.3s">
    <rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="14" fill="{c["panel"]}" stroke="{c["border"]}"/>
    <path d="M{px} {py + 14}a14 14 0 0 1 14-14h{pw - 28}a14 14 0 0 1 14 14v26H{px}z" fill="{c["panel_top"]}"/>
    <line x1="{px}" y1="{py + 40}" x2="{px + pw}" y2="{py + 40}" stroke="{c["border"]}"/>
    <circle cx="{px + 22}" cy="{py + 20}" r="5.5" fill="#FF5F57"/>
    <circle cx="{px + 40}" cy="{py + 20}" r="5.5" fill="#FEBC2E"/>
    <circle cx="{px + 58}" cy="{py + 20}" r="5.5" fill="#28C840"/>
    <text x="{px + pw / 2}" y="{py + 25}" text-anchor="middle" fill="{c["faint"]}" font-family="{mono}" font-size="12">~/status · updated {updated}</text>
    <text x="{px + 28}" y="{py + 74}" fill="{c["faint"]}" font-family="{mono}" font-size="15">$</text>
    <text x="{px + 46}" y="{py + 74}" fill="{c["text"]}" font-family="{mono}" font-size="15">whoami</text>
    <circle class="pulse" cx="{px + pw - 30}" cy="{py + 69}" r="4.5" fill="{c["green"]}"/>
    <text x="{px + pw - 42}" y="{py + 74}" text-anchor="end" fill="{c["green"]}" font-family="{mono}" font-size="13">online</text>
  </g>
  {"".join(rows)}
  <rect class="cursor" x="{px + 28}" y="{cursor_y - 14}" width="9" height="18" fill="{c["accent"]}"/>
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
    readme = ROOT / "README.md"
    readme.write_text(replace_section(readme.read_text(encoding="utf-8"), "SHIPPED", render_shipped(p)), encoding="utf-8")
    print(f"repos={p.repos} stars={p.stars} followers={p.followers} release={p.release} "
          f"live={p.live_proxies} shipped={len(p.shipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
