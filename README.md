<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/header-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="./assets/header-light.svg">
    <img src="./assets/header-dark.svg" alt="Maximilian Feix — backend, infrastructure, automation" width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/maximilianfeix/proxy-scraper"><img src="https://img.shields.io/badge/featured-proxy--scraper-38BDF8?style=flat-square&logo=python&logoColor=white&labelColor=0D1B2A" alt="Featured project: proxy-scraper"></a>
  <a href="https://github.com/maximilianfeix?tab=repositories"><img src="https://img.shields.io/badge/repositories-browse-34D399?style=flat-square&logo=github&logoColor=white&labelColor=0D1B2A" alt="Repositories"></a>
  <img src="https://img.shields.io/badge/based_in-Germany-8BA3B8?style=flat-square&labelColor=0D1B2A" alt="Based in Germany">
</p>

## 👋 About

Software developer from Germany, working at a hosting company. Most of my time goes into the parts users never see: APIs, deployment pipelines, database schemas and the automation that keeps all of it running without me.

<table>
<tr>
<td width="50%" valign="top">

**What I do**

- Backend services in **Node.js**, **TypeScript** and **PHP**, with **Vue** where a UI is needed
- The ops half of the job: **Linux**, **Apache**, **Redis**, **MariaDB**, cron and shell glue
- Automation that removes repetitive work – CI pipelines, scripts, bots

</td>
<td width="50%" valign="top">

**Right now**

- 🔨 Building **devprofile.dev**
- 📚 Learning **microservices** – service boundaries, messaging, observability
- ⚡ Maintaining **[proxy-scraper](https://github.com/maximilianfeix/proxy-scraper)**

</td>
</tr>
</table>

## 🧰 Tech stack

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: light)" srcset="https://skillicons.dev/icons?i=ts,js,php,py,java,cpp,html,css&theme=light&perline=12">
    <img src="https://skillicons.dev/icons?i=ts,js,php,py,java,cpp,html,css&theme=dark&perline=12" alt="TypeScript, JavaScript, PHP, Python, Java, C++, HTML, CSS" height="44">
  </picture>
</p>
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: light)" srcset="https://skillicons.dev/icons?i=nodejs,vue,vite,mysql,mongodb,redis,sqlite&theme=light&perline=12">
    <img src="https://skillicons.dev/icons?i=nodejs,vue,vite,mysql,mongodb,redis,sqlite&theme=dark&perline=12" alt="Node.js, Vue, Vite, MySQL, MongoDB, Redis, SQLite" height="44">
  </picture>
</p>
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: light)" srcset="https://skillicons.dev/icons?i=linux,bash,githubactions,git,gitlab,figma,ps,ae,blender&theme=light&perline=12">
    <img src="https://skillicons.dev/icons?i=linux,bash,githubactions,git,gitlab,figma,ps,ae,blender&theme=dark&perline=12" alt="Linux, Bash, GitHub Actions, Git, GitLab, Figma, Photoshop, After Effects, Blender" height="44">
  </picture>
</p>

## 🛠️ How I work

| Principle | In practice |
|---|---|
| **Tested** | Tests that run offline and in CI – [proxy-scraper](https://github.com/maximilianfeix/proxy-scraper/actions/workflows/tests.yml) runs 450+ of them on Linux, macOS and Windows, against fake proxies and honeypots on `localhost` |
| **Reviewed** | Changes start as an issue and land through a reviewed pull request – see the [proxy-scraper history](https://github.com/maximilianfeix/proxy-scraper/pulls?q=is%3Apr+is%3Amerged) |
| **Automated** | Lint, CodeQL, Dependabot, tagged releases and scheduled jobs on GitHub Actions – this profile updates itself too |
| **Documented** | READMEs with a quick start, a changelog, contributing and security guides |

<details>
<summary><b>From commit to production – and which tool for which job</b></summary>

<br>

```mermaid
flowchart LR
    dev["Local dev<br/>Vue + Vite"] --> push["git push"]
    push --> ci["GitHub Actions<br/>lint, test, build"]
    ci --> art["Artifact"]
    art --> web["Apache / Node.js"]
    web --> api["API layer<br/>PHP, Node"]
    api --> cache[("Redis<br/>cache, sessions")]
    api --> db[("MariaDB<br/>MongoDB")]
    web --> obs["Logs, metrics,<br/>alerting"]
    obs -.->|"something broke"| dev

    classDef node fill:#152A3D,stroke:#38BDF8,stroke-width:1px,color:#E6EDF3
    classDef store fill:#0F2233,stroke:#34D399,stroke-width:1px,color:#E6EDF3
    class dev,push,ci,art,web,api,obs node
    class cache,db store
```

**What I reach for, and when**

```mermaid
flowchart TD
    q{"What kind of job?"}
    q -->|"HTTP API, realtime"| n["Node.js"]
    q -->|"classic web app, CMS"| p["PHP"]
    q -->|"scripting, glue, tooling"| py["Python"]
    q -->|"user interface"| v["Vue + Vite"]
    n --> d1{"Data shape?"}
    p --> d1
    d1 -->|"relational"| m["MariaDB / MySQL"]
    d1 -->|"documents"| mo["MongoDB"]
    d1 -->|"hot, short-lived"| r["Redis"]
    d1 -->|"single file, embedded"| s["SQLite"]

    classDef node fill:#152A3D,stroke:#38BDF8,stroke-width:1px,color:#E6EDF3
    classDef decision fill:#0F2233,stroke:#8BA3B8,stroke-width:1px,color:#E6EDF3
    class n,p,py,v,m,mo,r,s node
    class q,d1 decision
```

</details>

## ⭐ Featured project

<table>
<tr>
<td>

### ⚡ [proxy-scraper](https://github.com/maximilianfeix/proxy-scraper)

**Free proxies that actually work.** Scrapes HTTP/SOCKS4/SOCKS5 proxies from 700+ sources and verifies every hit: honeypot filter, catches proxies that inject scripts (one in five does), HTTPS with verified TLS, anonymity, country and provider. It learns with every run which sources are worth it. Comes with a setup wizard, a live dashboard, a rotating proxy server (SOCKS5 + HTTP, sticky sessions, country per request, Prometheus metrics), a Python API and shell completion.

**→ [Browse the live list](https://maximilianfeix.github.io/proxy-scraper/)**, re-checked every 6 hours by GitHub Actions.

<a href="https://github.com/maximilianfeix/proxy-scraper/actions/workflows/tests.yml"><img src="https://github.com/maximilianfeix/proxy-scraper/actions/workflows/tests.yml/badge.svg" alt="tests"></a> <a href="https://github.com/maximilianfeix/proxy-scraper/releases/latest"><img src="https://img.shields.io/github/v/release/maximilianfeix/proxy-scraper?style=flat-square&color=38BDF8" alt="release"></a> <a href="https://github.com/maximilianfeix/proxy-scraper/tree/proxy-list"><img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmaximilianfeix%2Fproxy-scraper%2Fproxy-list%2Fbadges%2Ftotal.json&style=flat-square" alt="live proxies"></a> <a href="https://github.com/maximilianfeix/proxy-scraper/stargazers"><img src="https://img.shields.io/github/stars/maximilianfeix/proxy-scraper?style=flat-square&color=FBBF24" alt="stars"></a>

| 700+ | ~1M | 25 s | 3 OS |
|:---:|:---:|:---:|:---:|
| sources | candidates per run | to check them | Linux · macOS · Windows |

<a href="https://maximilianfeix.github.io/proxy-scraper/"><img src="https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/main/docs/website.png" alt="The live proxy list website" width="100%"></a>

<sub>Python · asyncio · rich · Docker · GitHub Actions + Pages · 400+ offline tests on three operating systems</sub>

</td>
</tr>
</table>

## 🚀 Recently shipped

<!--SHIPPED:start-->
- 🔀 Merged [--serve-host for Docker](https://github.com/maximilianfeix/proxy-scraper/pull/57) in **proxy-scraper** <sub>· 25 Sep 2026</sub>
- 🔀 Merged [Website: provider column and datacenter filter](https://github.com/maximilianfeix/proxy-scraper/pull/58) in **proxy-scraper** <sub>· 25 Sep 2026</sub>
- 🔀 Merged [Provider per proxy and --no-datacenter](https://github.com/maximilianfeix/proxy-scraper/pull/56) in **proxy-scraper** <sub>· 25 Sep 2026</sub>
- 🔀 Merged [Proxy server v2: strategies, sessions, SOCKS5, status](https://github.com/maximilianfeix/proxy-scraper/pull/55) in **proxy-scraper** <sub>· 25 Sep 2026</sub>
- 🔀 Merged [Live list website](https://github.com/maximilianfeix/proxy-scraper/pull/52) in **proxy-scraper** <sub>· 25 Sep 2026</sub>
- 🔀 Merged [Catch proxies that inject scripts](https://github.com/maximilianfeix/proxy-scraper/pull/51) in **proxy-scraper** <sub>· 25 Sep 2026</sub>
<!--SHIPPED:end-->

## 📂 More projects

<p align="center">
  <img src="./assets/projects.svg" alt="More repositories: AxonPHPCLI, Mini-Laravel, C++ template for macOS, CurrentlyFreeDomains" width="100%">
</p>

## 📈 GitHub activity

<p align="center">
  <img src="./assets/metrics.svg" alt="GitHub metrics: activity, community, repositories, languages and contribution calendar">
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/maximilianfeix/maximilianfeix/output/github-snake-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/maximilianfeix/maximilianfeix/output/github-snake.svg">
    <img src="https://raw.githubusercontent.com/maximilianfeix/maximilianfeix/output/github-snake.svg" alt="Contribution snake" width="100%">
  </picture>
</p>

## ⚙️ Powered by GitHub Actions

This profile keeps itself up to date:

| Workflow | Status | What it does | When |
|---|---|---|---|
| [Profile](https://github.com/maximilianfeix/maximilianfeix/actions/workflows/profile.yml) | [![Profile](https://github.com/maximilianfeix/maximilianfeix/actions/workflows/profile.yml/badge.svg)](https://github.com/maximilianfeix/maximilianfeix/actions/workflows/profile.yml) | renders the banner with live data and the *Recently shipped* list ([script](scripts/build_profile.py)) | every 3 hours |
| [Metrics](https://github.com/maximilianfeix/maximilianfeix/actions/workflows/metrics.yml) | [![Metrics](https://github.com/maximilianfeix/maximilianfeix/actions/workflows/metrics.yml/badge.svg)](https://github.com/maximilianfeix/maximilianfeix/actions/workflows/metrics.yml) | activity, languages, calendar and project cards via [lowlighter/metrics](https://github.com/lowlighter/metrics) | nightly |
| [Contribution snake](https://github.com/maximilianfeix/maximilianfeix/actions/workflows/main.yml) | [![Snake](https://github.com/maximilianfeix/maximilianfeix/actions/workflows/main.yml/badge.svg)](https://github.com/maximilianfeix/maximilianfeix/actions/workflows/main.yml) | turns the contribution graph into the snake above | nightly |
| [Link check](https://github.com/maximilianfeix/maximilianfeix/actions/workflows/links.yml) | [![Link check](https://github.com/maximilianfeix/maximilianfeix/actions/workflows/links.yml/badge.svg)](https://github.com/maximilianfeix/maximilianfeix/actions/workflows/links.yml) | makes sure every link in this README still works | weekly |

---

<p align="center">
  <sub>Open to interesting backend and infrastructure work – the easiest way to reach me is an issue or discussion on one of my repositories.</sub><br>
  <sub>Banner, project cards and stats are generated in this repository by GitHub Actions.</sub>
</p>
