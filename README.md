<!--
  Profile README for github.com/maximilianfeix
  Assets live in /assets, automation in /.github/workflows
  Search for "TODO" to find the spots you should personalise.
-->

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/header-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="./assets/header-light.svg">
    <img src="./assets/header-dark.svg" alt="Maximilian Feix — backend, infrastructure, automation" width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://discord.gg/0d6v"><img src="https://img.shields.io/badge/Discord-5865F2?style=flat-square&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="mailto:TODO@example.com"><img src="https://img.shields.io/badge/Email-0D1B2A?style=flat-square&logo=maildotru&logoColor=38BDF8" alt="Email"></a>
  <a href="https://github.com/maximilianfeix?tab=repositories"><img src="https://img.shields.io/badge/Repositories-0D1B2A?style=flat-square&logo=github&logoColor=38BDF8" alt="Repositories"></a>
  <img src="https://komarev.com/ghpvc/?username=maximilianfeix&style=flat-square&color=38BDF8&label=views" alt="Profile views">
</p>

---

## About

Software developer from Germany, working at a hosting company. Most of my time goes into the parts users never see: APIs, deployment pipelines, database schemas and the automation that keeps all of it running without me.

- Building backend services in **Node.js** and **PHP**, with **Vue** on the front where a UI is needed
- Comfortable in the ops half of the job: **Apache**, **Redis**, **MariaDB**, cron and shell glue
- Interested in reliability, sensible defaults and scripts that remove repetitive work
- Currently digging deeper into **TODO: z. B. containers, Go, observability**

> Open to interesting backend or infrastructure projects. The fastest way to reach me is Discord.

---

## Stack

| | |
|---|---|
| **Languages** | ![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black) ![PHP](https://img.shields.io/badge/PHP-777BB4?style=flat-square&logo=php&logoColor=white) ![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat-square&logo=html5&logoColor=white) |
| **Runtime & frameworks** | ![Node.js](https://img.shields.io/badge/Node.js-5FA04E?style=flat-square&logo=nodedotjs&logoColor=white) ![Vue.js](https://img.shields.io/badge/Vue.js-4FC08D?style=flat-square&logo=vuedotjs&logoColor=white) ![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white) |
| **Data** | ![MariaDB](https://img.shields.io/badge/MariaDB-003545?style=flat-square&logo=mariadb&logoColor=white) ![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=flat-square&logo=mysql&logoColor=white) ![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=flat-square&logo=mongodb&logoColor=white) ![Redis](https://img.shields.io/badge/Redis-FF4438?style=flat-square&logo=redis&logoColor=white) ![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white) |
| **Infrastructure** | ![Linux](https://img.shields.io/badge/Linux-FCC624?style=flat-square&logo=linux&logoColor=black) ![Apache](https://img.shields.io/badge/Apache-D22128?style=flat-square&logo=apache&logoColor=white) ![GitHub Actions](https://img.shields.io/badge/Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white) ![Git](https://img.shields.io/badge/Git-F05032?style=flat-square&logo=git&logoColor=white) ![GitLab](https://img.shields.io/badge/GitLab-FC6D26?style=flat-square&logo=gitlab&logoColor=white) |
| **Design** | ![Figma](https://img.shields.io/badge/Figma-F24E1E?style=flat-square&logo=figma&logoColor=white) ![Photoshop](https://img.shields.io/badge/Photoshop-31A8FF?style=flat-square&logo=adobephotoshop&logoColor=white) ![Illustrator](https://img.shields.io/badge/Illustrator-FF9A00?style=flat-square&logo=adobeillustrator&logoColor=white) ![After Effects](https://img.shields.io/badge/After_Effects-9999FF?style=flat-square&logo=adobeaftereffects&logoColor=black) ![Blender](https://img.shields.io/badge/Blender-E87D0D?style=flat-square&logo=blender&logoColor=white) |

---

## How a change reaches production

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

<details>
<summary><b>What I reach for, and when</b></summary>

<br>

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

---

## Projects

<!-- TODO: Ersetze REPO_1 / REPO_2 durch echte Repository-Namen. Karten ohne gültiges Repo zeigen einen Fehler. -->

<p align="center">
  <a href="https://github.com/maximilianfeix/REPO_1">
    <img src="https://github-readme-stats.vercel.app/api/pin/?username=maximilianfeix&repo=REPO_1&theme=tokyonight&hide_border=true&bg_color=0D1B2A&title_color=38BDF8&text_color=8BA3B8&icon_color=34D399" alt="Project 1">
  </a>
  <a href="https://github.com/maximilianfeix/REPO_2">
    <img src="https://github-readme-stats.vercel.app/api/pin/?username=maximilianfeix&repo=REPO_2&theme=tokyonight&hide_border=true&bg_color=0D1B2A&title_color=38BDF8&text_color=8BA3B8&icon_color=34D399" alt="Project 2">
  </a>
</p>

---

## Activity

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github-readme-stats.vercel.app/api?username=maximilianfeix&show_icons=true&include_all_commits=true&hide_border=true&hide_title=true&bg_color=0D1B2A&text_color=8BA3B8&icon_color=38BDF8&ring_color=34D399">
    <source media="(prefers-color-scheme: light)" srcset="https://github-readme-stats.vercel.app/api?username=maximilianfeix&show_icons=true&include_all_commits=true&hide_border=true&hide_title=true&bg_color=F6F9FC&text_color=43647E&icon_color=0284C7&ring_color=10B981">
    <img src="https://github-readme-stats.vercel.app/api?username=maximilianfeix&show_icons=true&include_all_commits=true&hide_border=true" alt="GitHub stats" height="170">
  </picture>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github-readme-stats.vercel.app/api/top-langs/?username=maximilianfeix&layout=compact&langs_count=8&hide_border=true&hide_title=true&bg_color=0D1B2A&text_color=8BA3B8&title_color=38BDF8">
    <source media="(prefers-color-scheme: light)" srcset="https://github-readme-stats.vercel.app/api/top-langs/?username=maximilianfeix&layout=compact&langs_count=8&hide_border=true&hide_title=true&bg_color=F6F9FC&text_color=43647E&title_color=0284C7">
    <img src="https://github-readme-stats.vercel.app/api/top-langs/?username=maximilianfeix&layout=compact&langs_count=8&hide_border=true" alt="Top languages" height="170">
  </picture>
</p>

<p align="center">
  <img src="https://streak-stats.demolab.com?user=maximilianfeix&hide_border=true&background=0D1B2A&stroke=24405A&ring=38BDF8&fire=34D399&currStreakLabel=8BA3B8&sideLabels=8BA3B8&dates=5E7B94&currStreakNum=E6EDF3&sideNums=E6EDF3" alt="Contribution streak" height="170">
</p>

### Contribution graph

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/maximilianfeix/maximilianfeix/output/github-snake-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/maximilianfeix/maximilianfeix/output/github-snake.svg">
    <img src="https://raw.githubusercontent.com/maximilianfeix/maximilianfeix/output/github-snake.svg" alt="Contribution snake" width="100%">
  </picture>
</p>

<details>
<summary><b>Detailed metrics</b> (generated daily, served from this repo)</summary>

<br>

<p align="center">
  <img src="./assets/metrics.svg" alt="Detailed GitHub metrics" width="100%">
</p>

</details>

<details>
<summary><b>GitAnimals</b></summary>

<br>

<p align="center">
  <a href="https://github.com/devxb/gitanimals"><img src="https://render.gitanimals.org/lines/maximilianfeix" alt="GitAnimals"></a>
</p>

</details>

---

<p align="center">
  <sub>Banner and diagrams are hand-built and live in this repository. Stats and the snake refresh themselves every night via GitHub Actions.</sub>
</p>
