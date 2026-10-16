# Maintaining this profile

The README is mostly hand-written. A few parts are generated and rewritten between `<!--NAME:start-->` and `<!--NAME:end-->` markers. Don't edit inside the markers; the next run would undo it.

## What updates by itself

| What | Made by | When | Files |
|---|---|---|---|
| Version and download badges, the four activity numbers, the static contribution grid, *Recently shipped*, the notes on the numbers | [`profile.yml`](../.github/workflows/profile.yml) runs [`scripts/build_profile.py`](../scripts/build_profile.py) | every 3 hours; downloads at most once per 20 hours | `data/`, `assets/stats-*.svg`, `assets/snake/contributions-static-*.svg`, `README.md` |
| The contribution snake | [`snake.yml`](../.github/workflows/snake.yml) with [Platane/snk](https://github.com/Platane/snk) `svg-only`, pinned to v3.5.0 (`d8f6715`) | daily at 04:37 UTC | `assets/snake/github-snake*.svg` |
| Link check | [`links.yml`](../.github/workflows/links.yml) | weekly and on README changes | none |

Both workflows can be started by hand under *Actions → Run workflow*. If a run fails, it commits nothing, so the last good files stay in place. The README only shows the snake once both snake files exist; until then it shows the static grid.

### The numbers

- **Stars**: the sum over my public, non-fork repositories.
- **PRs merged elsewhere / projects patched**: merged pull requests in public repositories owned by someone else. Repositories of my own accounts and organisations (repository variable `PROFILE_EXCLUDE_OWNERS`, comma-separated) and entries in `awesome` lists are left out. Private repositories never count, even when the token can see them. The search is paginated up to GitHub's 1,000-result limit; if GitHub reports incomplete results, the README says the figure is a lower bound.
- **Releases in 12 months**: published, non-draft releases of my public repositories, all pages, deduplicated by release id.
- **Downloads**: see the table in the README. npm and PyPI are 30-day windows, GitHub is all time over the program archives only. A failed fetch keeps the last value with its original date; nothing is ever shown as 0 because a source was down. GraphQL errors stop the run instead of turning partial data into numbers.

## What I update by hand

### The city (`assets/city/`)

Recorded from the published repoville demo, so the picture and the link show the same data. The recording script lives outside this repository and uses the Playwright of a repoville checkout:

```sh
ZOOM_OUT=6 node city-orbit.mjs <frames-dir> day 48
ZOOM_OUT=6 node city-orbit.mjs <frames-dir> night 48
```

It opens `https://maximilianfeix.github.io/repoville/r/maximilianfeix/repoville/?ui=off&quality=high` (`&time=night` for the dark version), zooms out with the mouse wheel and drags the viewer's own orbit controls a few pixels per frame, there and back. Frames are cropped to 2:1 and saved as an animated WebP (880×440, about 1 MB) plus a still JPEG for reduced motion. When the demo is rebuilt, update the commit, file and line counts in the caption: the commit is in the `site: deploy <sha>` message on repoville's `gh-pages` branch, the counts in the demo's `<meta name="description">`.

### Terminal pictures (`assets/projects/*.png`)

The `.ansi` files in `assets/projects/src/` are the unedited output of these runs:

| Picture | Command | Where |
|---|---|---|
| hexvero | `FORCE_COLOR=1 npx -y hexvero@0.7.5 analyze notesdesk-1.4.0.asar` | `examples/` of the hexvero repo |
| spillage | `spillage scan` (0.10.0) on a throwaway home built by `build_home()` from spillage's `docs/make_demo.py`, so only the fake keys of its test suite appear | spillage repo |
| dockdu | `scripts/demo-up.sh`, then `docker run --rm -t -e COLUMNS=92 -v /var/run/docker.sock:/var/run/docker.sock:ro -v /var/lib/docker:/var/lib/docker:ro ghcr.io/maximilianfeix/dockdu:v0.5.0 --top 3`, then `scripts/demo-down.sh` | dockdu repo, Docker Desktop |

`python3 scripts/render_terminal.py` turns them into `build/terminal/<name>.html` (which lines are shown is set in `SHOTS`); screenshot the `#shot` element at device scale 2 to get the PNG. Never run spillage on a real home directory for a picture.

The proxy-scraper picture is a screenshot of the live list on its website (1280 px wide at 2×, the table below "Pick your proxies").

### Icons (`assets/icons/`)

From [tandpfun/skill-icons](https://github.com/tandpfun/skill-icons) at `7f7e691`, MIT licence (copy in `assets/icons/LICENSE`). Only add a technology that a current public project uses.

### Featured projects and contributions

Hand-written in the README. Read a pull request before describing it, and link the PR itself. The badge rows under each project are generated: add or remove a project in `PROJECTS` in `scripts/build_profile.py` together with its `<!--BADGES:<slug>:start-->` / `<!--BADGES:<slug>:end-->` markers. Check a package's registry metadata and provenance before adding it: a package with the same name is not proof that it is mine.
