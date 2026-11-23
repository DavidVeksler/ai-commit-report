"""Shared config, identity and masking helpers for the report scripts."""
import functools
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
CONFIG = json.loads((ROOT / "data" / "report-config.json").read_text(encoding="utf-8"))
PROFILE = CONFIG["profile"]
USER = PROFILE["github_user"]
BOTS = set(PROFILE.get("bot_authors", []))
CLAUDE_AUTHOR = "noreply@anthropic.com"


def gh_token():
    """Token for the configured account; falls back to gh's active account."""
    r = subprocess.run(["gh", "auth", "token", "--user", USER], capture_output=True, text=True)
    if r.returncode:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
    return r.stdout.strip()


def gh_env():
    return {**os.environ, "GH_TOKEN": gh_token()}


def git_email():
    r = subprocess.run(["git", "config", "--global", "user.email"], capture_output=True, text=True)
    return r.stdout.strip().lower()


def identity():
    """Emails and patterns that mark a commit as the report owner's.

    Built at run time from the GitHub account (written by collect.py to
    .cache/identity.json), the local git config and COMMIT_REPORT_EMAILS, so no
    address has to be committed to the config.
    """
    emails = set()
    cached = CACHE / "identity.json"
    if cached.exists():
        emails.update(json.loads(cached.read_text(encoding="utf-8")).get("emails", []))
    if git_email():
        emails.add(git_email())
    emails.update(e.strip().lower() for e in os.environ.get("COMMIT_REPORT_EMAILS", "").split(",") if e.strip())
    patterns = [re.compile(p, re.I) for p in PROFILE.get("identity_patterns", [])]
    return emails, patterns


@functools.cache
def _ident():
    return identity()


def is_me(name, email):
    emails, patterns = _ident()
    return email.lower() in emails or any(p.search(name + " " + email) for p in patterns)


def mask_key(name):
    return "sha256:" + hashlib.sha256(name.lower().encode()).hexdigest()


def _listed(name, entries):
    return any(e.lower() == name.lower() or e == mask_key(name) for e in entries)


def owner_masked(owner):
    return _listed(owner, CONFIG.get("mask_owners", []))


def repo_masked(full):
    return owner_masked(full.split("/")[0]) or _listed(full, CONFIG.get("mask_repos", []))
