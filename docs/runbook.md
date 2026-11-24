# Runbook: refresh and publish David's demo

The tool itself (setup, config, scripts, counting rules) is documented in `README.md`. This runbook covers only David's instance at https://davidveksler.com/commits/.

## Update the live demo (fast path)

When David says "update the commits page", run one command and read only its last lines. Do not re-read the scripts, config or page source.

```powershell
scripts\publish.ps1              # full refresh from GitHub, ~2 min
scripts\publish.ps1 -SkipFetch   # reuse cached clones, ~30 s
scripts\publish.ps1 -NoDeploy    # stop after committing
```

It refreshes the data, rebuilds, copies into `../davidveksler.com/public/commits/`, commits and pushes both repos, runs that site's guarded deploy, and fails unless the live page shows today's `asof`. Success ends with `Live: https://davidveksler.com/commits/ now shows <date>, <n> commits`. Tested 2026-11-23 (11,237 commits).

- Publishing is a deploy, so run it only when David asks to publish or update the live page.
- It refuses to run if `davidveksler.com` has uncommitted changes. Commit or stash them and rerun.
- If it says "Site already current", nothing changed.
- Report the new total and date to David, nothing more.

## Manual steps (only when debugging)

```powershell
scriptsefresh.ps1 [--skip-fetch]                         # collect, sessions, aggregate, build, og
python scripts/aggregate.py ; python scripts/build.py ; python scripts/og.py   # config-only change
python scripts/sync_site.py                                # copy into ../davidveksler.com
```

David's commit addresses come from `git config user.email` plus the `veksler` pattern in the config; no address is stored in the repo. The claude.ai artifact (private) is separate: republish `dist/artifact.html` to https://claude.ai/artifact/6goDZMhebhQoxZHHMU3PGb.

## Known limits

- Claude Code transcripts on disk start 2026-07-23, so the "one prompt, N actions" section covers July onward; the page reads the range from `stats.sessions.first_day` / `last_day`.
- Shell calls are grouped by the first program in each command; `$VAR` executables and odd constructs land in "Other shell commands".
- ChatGPT commits leave no trailer. `scripts/chatgpt_estimate.py` gives a bounded estimate, not a count.
- Reconcile (2026-11-22): GitHub shows about 11,498 commits for the trailing year; this report counts 11,430 of David's own, 10,628 of them the way GitHub counts (default branch, profile email, no merges).
