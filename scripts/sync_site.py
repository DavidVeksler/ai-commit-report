"""Copy the built page and social card into a website checkout.

Target: `site.publish_dir` in data/report-config.json (relative to this repo),
or the first argument. Copies only; committing and deploying the site is a
separate, deliberate step in that repo.

Usage: python scripts/sync_site.py [target-dir]
"""
import shutil
import sys
from pathlib import Path

from common import CONFIG, ROOT


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else CONFIG.get("site", {}).get("publish_dir")
    if not target:
        sys.exit("no target: pass a directory or set site.publish_dir in data/report-config.json")
    site = (ROOT / target).resolve()
    for name in ("index.html", "og.png"):
        if not (ROOT / "dist" / name).exists():
            sys.exit(f"dist/{name} missing; run scripts/build.py and scripts/og.py first")
    site.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "og.png"):
        shutil.copy2(ROOT / "dist" / name, site / name)
        print(f"copied dist/{name} -> {site / name}")


if __name__ == "__main__":
    main()
