"""Estimate how many of the owner's commits came from ChatGPT/Codex, which leave no Claude trailer.

Assumes the owner writes a subject line only by hand, so a commit with a body (a description) and no
Claude trailer is a ChatGPT/Codex candidate. Each candidate is then checked
against the local Claude Code transcripts (a subject that appears in a
transcript's `git commit` call was made by Claude with the trailer stripped).
Candidates older than the oldest transcript on disk stay unverified.

Usage: python scripts/chatgpt_estimate.py
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate as a  # noqa: E402

HOME = Path.home()
TRAILER_LINE = re.compile(r"^[A-Za-z-]+: .+<.+>$")


def description(r):
    return "\n".join(l for l in r["body"].splitlines() if l.strip() and not TRAILER_LINE.match(l.strip()))


def transcript_text():
    blobs = {"claude": [], "codex": []}
    for src, root in (("claude", HOME / ".claude/projects"), ("codex", HOME / ".codex/sessions")):
        for p in root.rglob("*.jsonl"):
            with p.open(encoding="utf-8", errors="replace") as fh:
                blobs[src] += [line for line in fh if "commit" in line]
    return {k: "\n".join(v) for k, v in blobs.items()}


def main():
    rows = [r for r in a.load() if r["role"] == "me" and r["local"].year == a.YEAR and r["parents"] < 2
            and not a.repo_masked(r["repo"])]
    codex_tagged = [r for r in rows if a.classify(r, r["trailers"]) == "codex"]
    candidates = [r for r in rows if a.classify(r, r["trailers"]) == "untagged" and description(r)]
    blob = transcript_text()
    verdict = collections.Counter()
    for r in candidates:
        key = json.dumps(r["subject"][:60])[1:-1]
        where = "claude" if key in blob["claude"] else "codex" if key in blob["codex"] else "unmatched"
        month = r["local"].strftime("%Y-%m")
        verdict[(month, where)] += 1
    print(f"Codex-tagged (trailer): {len(codex_tagged)}")
    print(f"No Claude trailer, with a description: {len(candidates)}")
    for month in sorted({m for m, _ in verdict}):
        c, x, u = (verdict[(month, w)] for w in ("claude", "codex", "unmatched"))
        print(f"  {month}: {c + x + u:>4} candidates | found in Claude transcript {c:>3} | found in Codex transcript {x:>3} | unmatched {u:>3}")
    unmatched = sum(v for (m, w), v in verdict.items() if w == "unmatched")
    days = sorted(json.loads((a.CACHE / "sessions.json").read_text()).get("claude_by_day", {})) if (a.CACHE / "sessions.json").exists() else []
    first = days[0][:7] if days else "9999"
    print(f"Unmatched total: {unmatched}; unmatched since transcripts begin ({first}): "
          f"{sum(v for (m, w), v in verdict.items() if w == 'unmatched' and m >= first)}")


if __name__ == "__main__":
    main()
