"""Inject data/stats.json and the profile into src/report.html.

Writes into dist/:
  artifact.html  body fragment (for viewers that supply their own document skeleton, such as claude.ai Artifacts)
  index.html     standalone page with full head (title, description, canonical, Open Graph, JSON-LD)
  (og.png is made separately by scripts/og.py)

Page text comes from data/report-config.json: `profile` fills the page,
`site` fills the head tags.

Usage: python scripts/build.py
"""
import json
import re
from html import escape

from common import CONFIG, PROFILE, ROOT

TOOL_URL = "https://github.com/DavidVeksler/ai-commit-report"
SITE = CONFIG.get("site", {})


def links_html():
    out = []
    for link in PROFILE.get("links", []):
        cls = "btn primary" if link.get("primary") else "btn"
        out.append(f'<a class="{cls}" href="{escape(link["href"], quote=True)}">{escape(link["label"])}</a>')
    return "\n    ".join(out)


def playbook_html():
    path = PROFILE.get("playbook")
    if not path or not (ROOT / path).exists():
        return ""
    return re.sub(r"<!--.*?-->\s*", "", (ROOT / path).read_text(encoding="utf-8"), count=1, flags=re.S).strip()


def head(stats):
    title = SITE.get("title") or f"{stats['year']} in Commits — {PROFILE['name']}"
    desc = SITE.get("description") or f"{PROFILE['name']}'s {stats['year']} GitHub history: commits, AI co-authors, and when they landed."
    p = {k: escape(v, quote=True) for k, v in {**SITE, "title": title, "description": desc}.items() if isinstance(v, str)}
    author = {"@type": "Person", "name": PROFILE["name"], "url": SITE.get("author_url") or f"https://github.com/{PROFILE['github_user']}"}
    if SITE.get("person_id"):
        author["@id"] = SITE["person_id"]
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": title, "description": desc, "author": author, "dateModified": stats["asof"]}
    if SITE.get("canonical"):
        ld["url"] = SITE["canonical"]
    if SITE.get("website_id"):
        ld["isPartOf"] = {"@id": SITE["website_id"]}
    tags = [f"<title>{p['title']}</title>", f'<meta name="description" content="{p["description"]}">']
    if SITE.get("canonical"):
        tags.append(f'<link rel="canonical" href="{p["canonical"]}">')
    tags += ['<meta property="og:type" content="website">', f'<meta property="og:title" content="{p["title"]}">',
             f'<meta property="og:description" content="{p["description"]}">']
    if SITE.get("canonical"):
        tags.append(f'<meta property="og:url" content="{p["canonical"]}">')
    if SITE.get("og_image"):
        tags.append(f'<meta property="og:image" content="{p["og_image"]}">')
    tags += ['<meta name="twitter:card" content="summary_large_image">', f'<meta name="twitter:title" content="{p["title"]}">']
    if SITE.get("og_image"):
        tags.append(f'<meta name="twitter:image" content="{p["og_image"]}">')
    tags.append(f'<script type="application/ld+json">{json.dumps(ld)}</script>')
    return "\n".join(tags), title, desc


def main():
    stats = json.loads((ROOT / "data" / "stats.json").read_text(encoding="utf-8"))
    # Fields the page never reads stay out of the published source.
    for unused in ("top_words", "top_verbs", "hour_dow", "worktree_agent_merges"):
        stats.pop(unused, None)
    page = (ROOT / "src" / "report.html").read_text(encoding="utf-8")
    tokens = {
        "__PLAYBOOK__": playbook_html(),
        "__LINKS__": links_html(),
        "__NAME__": escape(PROFILE["name"]),
        "__GITHUB_USER__": escape(PROFILE["github_user"]),
        "__YEAR__": str(stats["year"]),
        "__GOAL__": f"{stats['goal']:,}",
        "__TZ__": escape(PROFILE.get("timezone_label", "local time")),
        "__TOOL_URL__": TOOL_URL,
        "__STATS__": json.dumps(stats, separators=(",", ":")),  # last, so stats text is never re-scanned for tokens
    }
    for token, value in tokens.items():
        assert token in page, f"{token} missing from src/report.html"
        page = page.replace(token, value)
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "artifact.html").write_text(page, encoding="utf-8")

    # Standalone: lift the fragment's <title> and artifact-only meta out of the body.
    body = re.sub(r"<title>.*?</title>\s*", "", page, count=1, flags=re.S)
    body = re.sub(r'<meta name="claude:[^>]*>\s*', "", body)
    tags, title, desc = head(stats)
    standalone = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        f"{tags}\n"
        "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n"
        "</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    )
    (dist / "index.html").write_text(standalone, encoding="utf-8")
    print(f"dist/artifact.html {len(page) // 1024} KB, dist/index.html {len(standalone) // 1024} KB, title {len(title)} chars, description {len(desc)} chars")


if __name__ == "__main__":
    main()
