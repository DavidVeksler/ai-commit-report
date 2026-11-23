# AGENTS.md

`ai-commit-report`: an open-source tool (public repo, MIT) that turns a GitHub account's commit history into a one-page interactive report. This checkout also holds David's own instance, published at https://davidveksler.com/commits/ as the demo. Global rules: `~/AGENTS.md`.

| Task | Read this |
| --- | --- |
| What the tool does, setup, every config field | `README.md` |
| Refresh David's numbers and publish the demo | `docs/runbook.md` |
| Change a knob (profile, site head tags, workday, masking, chart rows) | `data/report-config.json` |
| Rename or reveal a repo in the bubble chart | `data/display-names.json` |
| Change the playbook section (demo only) | `data/playbook.html` |
| Change the page design or copy | `src/report.html` (template; `__TOKENS__` are filled by `scripts/build.py`) |
| Change identity matching, masking, config loading | `scripts/common.py` |
| Change what counts as a commit, AI attribution, tool grouping | `scripts/aggregate.py` |
| Check the numbers against GitHub's profile graph | `scripts/reconcile.py` |
| Content quick path (`docs/content.md`) | N/A: one generated page |
| Marketing quick path (`docs/marketing.md`) | N/A: the page lives on davidveksler.com, see that repo's marketing docs |
| SEO progress log (`docs/seo-progress.md`) | N/A |

## Rules

- **This repo is public.** Never commit an email address, a masked owner or repo name, or anything from `.cache/`. Identity addresses come from the GitHub API, `git config` and the `COMMIT_REPORT_EMAILS` env var at run time; masks for private names use `sha256:` entries (`scripts/mask.py`).
- `.cache/` holds raw commit text and private repo names. It is gitignored and must never be committed or published. Only `data/stats.json` (aggregates) and `dist/` leave it.
- A repo shows no title (a bare commit number) when it is private and not in `data/display-names.json`, or when it matches `mask_owners` / `mask_repos`. Masked repos are also kept out of the word stats. Do not unmask a repo David has not approved for a public, hiring-manager audience.
- Nothing personal is hardcoded in scripts or the template: names, links and head tags come from `profile` and `site` in the config, so anyone can fork and run it.
- Headline counting rule: commits authored under the owner's identities, any branch, every repo the account owns or belongs to, work org included. Claude worktree agents and cron bots are reported separately.
- Copy follows David-voice rules: no em dashes in page copy, no unverifiable claims. Every number on the page comes from `data/stats.json`.
- Publishing to davidveksler.com is a deploy and needs David's go-ahead each time (`docs/runbook.md`).
