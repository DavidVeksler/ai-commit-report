# Runbook: refresh and publish David's demo

The tool itself (setup, config, scripts, counting rules) is documented in `README.md`. This runbook covers only David's instance at https://davidveksler.com/commits/.

## Refresh

```powershell
scripts\refresh.ps1                # live data; or: bash scripts/refresh.sh
scripts\refresh.ps1 --skip-fetch   # reuse the cached clones
```

Config-only change (workday, masking, links, chart rows):

```powershell
python scripts/aggregate.py ; python scripts/build.py ; python scripts/og.py
```

David's commit addresses are matched from `git config user.email` on this machine plus the `veksler` pattern in the config; no address is stored in the repo.

## Publish (needs David's go-ahead each time)

- **davidveksler.com/commits/:** `python scripts/sync_site.py` (copies into `../davidveksler.com/public/commits/`), then in `~/Projects/davidveksler.com` commit and run `npm run deploy:win -- -Yes`. Verify with `curl -s https://davidveksler.com/commits/ | grep <asof date>`. That repo links the page from `/projects/`, lists it in the sitemap (`customPages`) and in `public/llms.txt`.
- **claude.ai artifact (private):** republish `dist/artifact.html` to https://claude.ai/artifact/6goDZMhebhQoxZHHMU3PGb with the Artifact tool.

## Known limits

- Claude Code transcripts on disk start 2026-07-23, so the "one prompt, N actions" section covers July onward; the page reads the range from `stats.sessions.first_day` / `last_day`.
- Shell calls are grouped by the first program in each command; `$VAR` executables and odd constructs land in "Other shell commands".
- ChatGPT commits leave no trailer. `scripts/chatgpt_estimate.py` gives a bounded estimate, not a count.
- Reconcile (2026-11-22): GitHub shows about 11,498 commits for the trailing year; this report counts 11,430 of David's own, 10,628 of them the way GitHub counts (default branch, profile email, no merges).
