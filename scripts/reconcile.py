"""Compare this report's counts with GitHub's own contribution graph.

GitHub's profile total is commits on default branches whose author email is on
the account, plus pull requests, issues and reviews, with private-repo items
folded into one "restricted" number. This script queries it for the trailing
12 months and prints each difference next to our count so the gap is explained,
not guessed at. Needs `gh` logged in as the configured account.

Usage: python scripts/reconcile.py [--asof YYYY-MM-DD]
"""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate as a  # noqa: E402
from common import gh_env, identity  # noqa: E402

QUERY = """query($f:DateTime!,$t:DateTime!){viewer{contributionsCollection(from:$f,to:$t){
totalCommitContributions totalIssueContributions totalPullRequestContributions
totalPullRequestReviewContributions restrictedContributionsCount
contributionCalendar{totalContributions}}}}"""


def github(start, end):
    env = gh_env()
    out = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-f", f"f={start}T00:00:00Z", "-f", f"t={end + dt.timedelta(days=1)}T00:00:00Z"],
        capture_output=True, text=True, check=True, env=env,
    ).stdout
    return json.loads(out)["data"]["viewer"]["contributionsCollection"]


def main():
    asof = dt.date.fromisoformat(sys.argv[sys.argv.index("--asof") + 1]) if "--asof" in sys.argv else dt.date.today()
    start = asof - dt.timedelta(days=364)
    g = github(start, asof)
    rows = [r for r in a.load() if start <= r["local"].date() <= asof]
    mine = [r for r in rows if r["role"] == "me"]
    # GitHub credits commits whose author email is on the account: approximated by
    # the noreply address, git config user.email and COMMIT_REPORT_EMAILS.
    profile_emails = identity()[0]
    gh_like = [r for r in mine if r["on_default"] and r["ae"].lower() in profile_emails and r["parents"] < 2]
    print(f"window {start} to {asof}")
    print(f"GitHub profile total            {g['contributionCalendar']['totalContributions']:>7,}")
    print(f"  public commits                {g['totalCommitContributions']:>7,}")
    print(f"  private (restricted)          {g['restrictedContributionsCount']:>7,}   (commits + PRs + issues in private repos)")
    print(f"  pull requests / issues / reviews {g['totalPullRequestContributions']:>4,} / {g['totalIssueContributions']:,} / {g['totalPullRequestReviewContributions']:,}")
    print(f"GitHub commits, approx          {g['totalCommitContributions'] + g['restrictedContributionsCount']:>7,}")
    print()
    print(f"report: all commits counted     {len(rows):>7,}   (every branch; owner, Claude, bots)")
    print(f"  excluding Claude/bot authors  {len(mine):>7,}")
    print(f"  default branch + profile email, no merges {len(gh_like):>7,}   <- the way GitHub counts")


if __name__ == "__main__":
    main()
