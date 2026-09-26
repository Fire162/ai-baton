# Badges — the shapes, and which one to use when

One badge per line under the title, plain flat shields.io style (the default — no `style=` needed). Replace
`<owner>/<repo>`, `<workflow>.yml` and `<package>` with the repo's real values, and check each URL answers before
committing (`curl -sfo /dev/null -w '%{http_code}\n' '<badge url>'` → `200`).

## The three every README carries

| Badge | When | Markdown |
|---|---|---|
| CI | the repo has a CI workflow | `[![CI](https://github.com/<owner>/<repo>/actions/workflows/<workflow>.yml/badge.svg)](https://github.com/<owner>/<repo>/actions/workflows/<workflow>.yml)` |
| Version | published to a registry | `[![PyPI](https://img.shields.io/pypi/v/<package>)](https://pypi.org/project/<package>/)` · `[![npm](https://img.shields.io/npm/v/<package>)](https://www.npmjs.com/package/<package>)` |
| Release | not on a registry, tagged on GitHub | `[![Release](https://img.shields.io/github/v/release/<owner>/<repo>)](https://github.com/<owner>/<repo>/releases)` |
| License | a `LICENSE` file exists | `[![License](https://img.shields.io/github/license/<owner>/<repo>)](LICENSE)` |

The GitHub-native CI badge (`…/badge.svg`) works on a private repo only for people who can see the repo; the
shields.io `github/*` badges need a public repo. No `LICENSE` yet → no license badge, and § License says so.

## Optional — only where the surface exists

| Badge | Markdown |
|---|---|
| Language versions | `[![Python](https://img.shields.io/pypi/pyversions/<package>)](https://pypi.org/project/<package>/)` |
| Coverage | the badge the coverage action publishes, linked to its report — never a static number |
| Docs site | `[![Docs](https://img.shields.io/badge/docs-<site>-blue)](<docs url>)` |
| PRs welcome | `[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)` |
| Claude Code plugin | `[![Claude Code plugin](https://img.shields.io/badge/Claude_Code-plugin-D97757)](#install)` — links the install section |

Never: a badge for a surface that does not exist (a chat server nobody runs), a static "build passing", a
stars/downloads vanity badge on a new repo, more than six.
