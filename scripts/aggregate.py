"""Turn .cache/commits.jsonl (+ .cache/sessions.json) into data/stats.json.

Only aggregates leave this script: counts, dates, public display names and
common commit-message words. No commit text and no names of masked repos.
All knobs live in data/report-config.json and data/display-names.json.

Headline counting rule: commits authored under the owner's identities (see
common.identity), on any branch, in every repo the account owns or belongs to.
Commits authored by Claude worktree agents and by the configured CI/cron bots
are counted apart as "agent_authored" because GitHub does not credit them to
the profile.
scripts/reconcile.py compares the result with GitHub's contribution graph.

Usage: python scripts/aggregate.py [--asof YYYY-MM-DD]
"""
import collections
import datetime as dt
import json
import re
import sys

from common import BOTS, CACHE, CLAUDE_AUTHOR, CONFIG, ROOT, USER, is_me, repo_masked  # noqa: F401

YEAR = CONFIG["year"]
GOAL = CONFIG["goal"]
TRAILER = re.compile(r"(?im)^co-authored-by:\s*(.+?)\s*<")
STOP = set("""a an and the to of in for on with from by at as is it its into via not no
vs be are was this that these those per all up out off new more any one two use when
don't doesn't can't won't""".split())


def model_family(name):
    m = re.match(r"Claude (Opus|Sonnet|Haiku|Fable) (\d+(?:\.\d+)?)", name)
    if not m:
        return None
    tier, ver = m.groups()
    return f"{tier} {'4.x' if float(ver) < 5 else ver}"


def classify(r, trailers):
    """AI attribution of one of the owner's commits, from its Co-Authored-By trailers."""
    t = " ".join(trailers).lower()
    if "claude" in t:
        return "claude"
    if "codex" in t or "openai" in t or "/codex/" in r["subject"].lower():
        return "codex"
    if "copilot" in t:
        return "copilot"
    return "untagged"


def role(r):
    if r["ae"] == CLAUDE_AUTHOR:
        return "agent"
    if r["an"] in BOTS:
        return "bot"
    return "me" if is_me(r["an"], r["ae"]) else None


def load():
    seen, rows = set(), []
    for line in (CACHE / "commits.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        if r["sha"] in seen:
            continue
        seen.add(r["sha"])
        r["role"] = role(r)
        if r["role"] == "bot" and r["fork"]:
            continue
        if r["role"]:
            r["local"] = dt.datetime.fromisoformat(r["ad"].replace("Z", "+00:00"))
            r["trailers"] = TRAILER.findall(r["body"])
            rows.append(r)
    return rows


def streaks(days):
    best = cur = 0
    best_end = prev = None
    for d in sorted(days):
        cur = cur + 1 if prev and (d - prev).days == 1 else 1
        if cur > best:
            best, best_end = cur, d
        prev = d
    return best, best_end


def minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def is_masked(full, meta, names):
    if repo_masked(full):
        return True
    return bool(meta.get("private", True)) and full not in names


def tool_rows(sess):
    """Human-readable action breakdown: shell calls grouped by what they run, other tools by name."""
    labels = CONFIG["tool_labels"]
    buckets = [(name, re.compile(rx)) for name, rx in CONFIG["shell_buckets"]]
    rows = collections.defaultdict(lambda: {"count": 0, "keys": collections.Counter()})
    for key, n in sess.get("shell_commands", {}).items():
        exe = (key.split() or ["(other)"])[0]
        label = next((name for name, rx in buckets if rx.search(exe)), "Other shell commands")
        rows[label]["count"] += n
        rows[label]["keys"][key] += n
    for name, n in sess.get("claude_tool_names", {}).items():
        if name in ("Bash", "PowerShell"):
            continue
        if name.startswith("mcp__Claude_Browser__"):
            label = labels["browser"]
        elif name.startswith("mcp__"):
            label = "Call a connected app"
        else:
            label = labels.get(name, name)
        rows[label]["count"] += n
    out = []
    for label, v in sorted(rows.items(), key=lambda kv: -kv[1]["count"])[: CONFIG["tool_chart_rows"]]:
        detail = "" if label == "Other shell commands" else ", ".join(k for k, _ in v["keys"].most_common(3) if not k.startswith("("))
        out.append({"label": label, "count": v["count"], "detail": detail})
    return out


def main():
    asof = dt.date.fromisoformat(sys.argv[sys.argv.index("--asof") + 1]) if "--asof" in sys.argv else dt.date.today()
    names = {k: v for k, v in json.loads((ROOT / "data" / "display-names.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
    repos = {r["full_name"]: r for r in json.loads((CACHE / "repos.json").read_text())}
    rows = [r for r in load() if r["local"].date() <= asof]
    mine = [r for r in rows if r["role"] == "me"]
    yr = [r for r in mine if r["local"].year == YEAR]

    by_year = collections.Counter(r["local"].year for r in mine if r["local"].year >= 2012)
    daily = collections.Counter(r["local"].date().isoformat() for r in yr)
    total = len(yr)
    agent_authored = collections.Counter(r["role"] for r in rows if r["role"] != "me" and r["local"].year == YEAR)

    start12 = asof - dt.timedelta(days=364)
    last12 = sum(1 for r in mine if start12 <= r["local"].date() <= asof)

    # Pace: trailing 30 days projects the rest of the year.
    last30 = sum(v for d, v in daily.items() if (asof - dt.date.fromisoformat(d)).days < 30)
    pace = last30 / 30
    days_left = (dt.date(YEAR, 12, 31) - asof).days
    projected = round(total + pace * days_left)
    eta = asof + dt.timedelta(days=-(-(GOAL - total) // pace)) if total < GOAL else None
    # Once past the goal, record the day the running count crossed it.
    reached, running = None, 0
    for d in sorted(daily):
        running += daily[d]
        if running >= GOAL:
            reached = d
            break

    work_start, work_end = minutes(CONFIG["workday"]["start"]), minutes(CONFIG["workday"]["end"])
    cats = collections.Counter()
    weekly_model = collections.defaultdict(collections.Counter)
    hour_dow = [[0] * 24 for _ in range(7)]
    half_hours = [0] * 48
    offhours = 0
    words = collections.Counter()
    verbs = collections.Counter()
    repo_n = collections.Counter()
    langs = collections.Counter()
    worktree_merges = 0
    ext_lang = {e: (name, spec["kind"]) for name, spec in CONFIG["languages"].items() if not name.startswith("_") for e in spec["ext"]}
    lang_commits = collections.Counter()
    lang_month = collections.defaultdict(collections.Counter)
    lang_repos = collections.defaultdict(set)
    lang_claude = collections.Counter()
    # First commit ever (all years) per language, to flag the ones new this year.
    lang_first = {}
    for r in mine:
        day = r["local"].date().isoformat()
        for e in r.get("exts", []):
            if e in ext_lang and (ext_lang[e][0] not in lang_first or day < lang_first[ext_lang[e][0]]):
                lang_first[ext_lang[e][0]] = day
    for r in yr:
        touched = {ext_lang[e] for e in r.get("exts", []) if e in ext_lang}
        cat = classify(r, r["trailers"])
        for name, _ in touched:
            lang_commits[name] += 1
            lang_month[r["local"].strftime("%Y-%m")][name] += 1
            lang_repos[name].add(r["repo"])
            lang_claude[name] += cat == "claude"
        cats[cat] += 1
        wk = (r["local"].date() - dt.timedelta(days=r["local"].weekday())).isoformat()
        for t in r["trailers"]:
            fam = model_family(t)
            if fam:
                weekly_model[wk][fam] += 1
                break
        hour_dow[r["local"].weekday()][r["local"].hour] += 1
        mod = r["local"].hour * 60 + r["local"].minute
        half_hours[mod // 30] += 1
        if not work_start <= mod < work_end:
            offhours += 1
        subj = r["subject"]
        if "worktree-agent" in subj:
            worktree_merges += 1
        # Masked repos stay out of the word stats so their vocabulary does not leak.
        if r["parents"] < 2 and not is_masked(r["repo"], repos.get(r["repo"], {}), names):
            toks = re.findall(r"[A-Za-z][A-Za-z\-']+", subj)
            if toks:
                verbs[toks[0].capitalize()] += 1
            words.update(w.lower() for w in toks if len(w) > 3 and w.lower() not in STOP)
        repo_n[r["repo"]] += 1
        if repos.get(r["repo"], {}).get("language"):
            langs[repos[r["repo"]]["language"]] += 1

    model_tot = collections.Counter()
    for c in weekly_model.values():
        model_tot.update(c)

    top_repos = []
    for full, n in repo_n.most_common(CONFIG["top_repos"]):
        meta = repos.get(full, {})
        masked = is_masked(full, meta, names)
        label = "" if masked else (names.get(full) or full.split("/")[1])
        top_repos.append({"name": label, "commits": n, "language": meta.get("language"), "masked": masked})

    kinds = {name: spec["kind"] for name, spec in CONFIG["languages"].items() if not name.startswith("_")}
    languages_touched = [
        {
            "name": n, "commits": c, "kind": kinds[n],
            "repos": len(lang_repos[n]),
            "claude_share": round(lang_claude[n] / c, 3),
            "first_ever": lang_first[n],
            "new_this_year": lang_first[n][:4] == str(YEAR),
        }
        for n, c in lang_commits.most_common()
    ]
    code_languages = [l for l in languages_touched if l["kind"] == "code" and l["commits"] >= CONFIG["language_min_commits"]]

    hours = collections.Counter(r["local"].hour for r in yr)
    busiest = daily.most_common(1)[0]
    per_hour = collections.Counter(r["local"].strftime("%Y-%m-%d %H") for r in yr).most_common(1)[0]
    streak, streak_end = streaks({dt.date.fromisoformat(d) for d in daily})
    first_big = min((d for d, v in daily.items() if v >= 10), default=None)
    month = collections.Counter(r["local"].strftime("%Y-%m") for r in yr)

    stats = {
        "asof": asof.isoformat(),
        "year": YEAR,
        "goal": GOAL,
        "total": total,
        "last12": {"start": start12.isoformat(), "end": asof.isoformat(), "total": last12},
        "agent_authored": {"claude_worktree_agents": agent_authored["agent"], "scheduled_jobs": agent_authored["bot"]},
        "projected": projected,
        "pace_30d": round(pace, 1),
        "goal_eta": eta.isoformat() if eta else None,
        "goal_reached": reached,
        "repos_scanned": len(repos),
        "repos_touched": len(repo_n),
        "languages_touched": languages_touched,
        "language_count": len(code_languages),
        "language_month": {m: dict(c) for m, c in sorted(lang_month.items())},
        "categories": dict(cats),
        "ai_trailer_share": round((cats["claude"] + cats["codex"] + cats["copilot"]) / total, 3),
        "daily": dict(sorted(daily.items())),
        "monthly": dict(sorted(month.items())),
        "by_year": {str(k): v for k, v in sorted(by_year.items())},
        "weekly_models": {k: dict(v) for k, v in sorted(weekly_model.items())},
        "model_totals": dict(model_tot.most_common()),
        "hour_dow": hour_dow,
        "half_hours": half_hours,
        "workday": CONFIG["workday"],
        "offhours_commits": offhours,
        "night_commits": sum(hours[h] for h in range(0, 6)),
        "weekend_commits": sum(1 for r in yr if r["local"].weekday() >= 5),
        "busiest_day": {"date": busiest[0], "commits": busiest[1]},
        "busiest_hour": {"hour": per_hour[0], "commits": per_hour[1]},
        "longest_streak": {"days": streak, "end": streak_end.isoformat() if streak_end else None},
        "first_10_commit_day": first_big,
        "worktree_agent_merges": worktree_merges,
        "top_repos": top_repos,
        "top_verbs": dict(verbs.most_common(14)),
        "top_words": dict(words.most_common(60)),
        "label_min_radius": CONFIG["label_min_radius"],
        "number_min_radius": CONFIG["number_min_radius"],
    }
    sess = CACHE / "sessions.json"
    if sess.exists():
        s = json.loads(sess.read_text())
        stats["sessions"] = {k: v for k, v in s.items() if isinstance(v, int)}
        days = sorted(s.get("claude_by_day", {}))
        if days:
            stats["sessions"]["first_day"], stats["sessions"]["last_day"] = days[0], min(days[-1], asof.isoformat())
        stats["tool_rows"] = tool_rows(s)
    out = ROOT / "data" / "stats.json"
    out.write_text(json.dumps(stats, indent=1))
    print(json.dumps({k: v for k, v in stats.items() if not isinstance(v, (dict, list))}, indent=1))
    print("categories", stats["categories"], "| agent-authored", stats["agent_authored"])
    print("models", stats["model_totals"])
    for row in stats.get("tool_rows", []):
        print(f"  {row['count']:>7,}  {row['label']}: {row['detail']}")


if __name__ == "__main__":
    main()
