"""Mirror every GitHub repo the configured account can see and dump raw commit metadata.

Blobless bare clones live in .cache/repos (gitignored); output is
.cache/commits.jsonl, one commit per line. Nothing private leaves .cache:
scripts/aggregate.py turns it into the committed data/stats.json.

Usage: python scripts/collect.py [--skip-fetch]
"""
import base64
import concurrent.futures as cf
import json
import subprocess
import sys

from common import CACHE, CONFIG, gh_env

REPOS = CACHE / "repos"
OUT = CACHE / "commits.jsonl"
EXCLUDED_OWNERS = set(CONFIG.get("exclude_owners", []))

SEP = "\x1f"
START = "\x1e"  # opens each commit record
HEAD_END = "\x1d"  # closes the header; --name-only file paths follow it
FMT = START + SEP.join(["%H", "%an", "%ae", "%aI", "%cn", "%ce", "%cI", "%P", "%s", "%b"]) + HEAD_END


def extension(path):
    """File extension (lowercase, with dot), or the bare name for extensionless files like Dockerfile."""
    name = path.rsplit("/", 1)[-1]
    return name.lower() if "." not in name.lstrip(".") else "." + name.rsplit(".", 1)[-1].lower()


def save_identity(env):
    """Record the account's noreply addresses so aggregate.py can match its commits."""
    me = json.loads(subprocess.run(["gh", "api", "user"], capture_output=True, text=True, check=True, env=env).stdout)
    emails = {f"{me['id']}+{me['login']}@users.noreply.github.com".lower(), f"{me['login']}@users.noreply.github.com".lower()}
    if me.get("email"):
        emails.add(me["email"].lower())
    (CACHE / "identity.json").write_text(json.dumps({"login": me["login"], "emails": sorted(emails)}, indent=1))


def list_repos(env):
    out = subprocess.run(
        ["gh", "api", "--paginate", "user/repos?per_page=100&affiliation=owner,collaborator,organization_member",
         "--jq", ".[] | {full_name, private, fork, language, size, pushed_at, html_url}"],
        capture_output=True, text=True, check=True, env=env,
    ).stdout
    repos = [json.loads(line) for line in out.splitlines() if line.strip()]
    return [r for r in repos if r["full_name"].split("/")[0] not in EXCLUDED_OWNERS]


def mirror(repo, env):
    dest = REPOS / (repo["full_name"].replace("/", "__") + ".git")
    url = f"https://github.com/{repo['full_name']}.git"
    # Auth via a per-invocation header so the token is never written to the clone's config.
    basic = base64.b64encode(f"x-access-token:{env['GH_TOKEN']}".encode()).decode()
    git = ["git", "-c", f"http.extraHeader=Authorization: Basic {basic}"]
    if dest.exists():
        cmd = git + ["-C", str(dest), "fetch", "--quiet", "--prune", url, "+refs/heads/*:refs/heads/*"]
    else:
        cmd = git + ["clone", "--quiet", "--bare", "--filter=blob:none", url, str(dest)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        return repo["full_name"], r.stderr.replace(env["GH_TOKEN"], "***").strip()[:200]
    return repo["full_name"], None


def default_branch_shas(dest):
    r = subprocess.run(["git", "-C", str(dest), "rev-list", "HEAD"], capture_output=True, text=True)
    return set(r.stdout.split())


def commits(repo):
    dest = REPOS / (repo["full_name"].replace("/", "__") + ".git")
    if not dest.exists():
        return []
    on_default = default_branch_shas(dest)
    r = subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(dest), "log", "--all", "--name-only", "--no-renames", f"--format={FMT}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    rows = []
    for rec in r.stdout.split(START)[1:]:
        head, _, files = rec.partition(HEAD_END)
        f = head.split(SEP)
        if len(f) < 10:
            continue
        exts = sorted({extension(p) for p in files.splitlines() if p.strip()})
        rows.append({
            "exts": exts,
            "repo": repo["full_name"], "private": repo["private"], "fork": repo["fork"],
            "language": repo["language"], "sha": f[0], "an": f[1], "ae": f[2], "ad": f[3],
            "on_default": f[0] in on_default, "cn": f[4], "ce": f[5], "cd": f[6], "parents": len(f[7].split()),
            "subject": f[8], "body": f[9],
        })
    return rows


def main():
    env = gh_env()
    REPOS.mkdir(parents=True, exist_ok=True)
    save_identity(env)
    repos = list_repos(env)
    (CACHE / "repos.json").write_text(json.dumps(repos, indent=1))
    print(f"{len(repos)} repos")
    if "--skip-fetch" not in sys.argv:
        with cf.ThreadPoolExecutor(8) as ex:
            for name, err in ex.map(lambda r: mirror(r, env), repos):
                if err:
                    print(f"  FAIL {name}: {err}", file=sys.stderr)
    n = 0
    with OUT.open("w", encoding="utf-8") as fh:
        for repo in repos:
            for row in commits(repo):
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
    print(f"{n} commits -> {OUT}")


if __name__ == "__main__":
    main()
