"""Sanity checks for sessions.primary_command. Run: python scripts/test_primary_command.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sessions import primary_command  # noqa: E402

CASES = {
    "cd /x && git -C foo commit -m 'a'": "git commit",
    "FOO=1 python - <<'EOF'\nprint(1)\nEOF": "python",
    '"$E" --headless x': "(variable)",
    "export GH_TOKEN=$(gh auth token) && gh api user": "gh api",
    "./scripts/deploy.sh --x": "script",
    "ls -la | head": "ls",
    "Get-ChildItem x": "Get-ChildItem",
    "timeout 30 curl -s http://x": "curl",
    "cd a; npm run build": "npm",
    "python3 scripts/x.py": "python",
    "": "(other)",
}


def main():
    bad = {c: (primary_command(c), want) for c, want in CASES.items() if primary_command(c) != want}
    for c, (got, want) in bad.items():
        print(f"FAIL {c!r}: got {got!r}, want {want!r}")
    print("ok" if not bad else f"{len(bad)} failed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
