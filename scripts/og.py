"""Render dist/og.png (1200x630 social card) from the hero of dist/index.html with a headless Chromium browser.

Looks for Edge, Chrome or Chromium; set BROWSER to a binary path to choose one.

Usage: python scripts/og.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from common import ROOT

CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
NAMES = ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "microsoft-edge", "msedge", "chrome"]


def browser():
    if os.environ.get("BROWSER"):
        return os.environ["BROWSER"]
    found = next((p for p in CANDIDATES if Path(p).exists()), None)
    return found or next((shutil.which(n) for n in NAMES if shutil.which(n)), None)


def main():
    exe = browser()
    if not exe:
        sys.exit("No Chromium-based browser found; install Chrome/Edge/Chromium or set BROWSER. dist/index.html is built; only the social card is missing.")
    src = (ROOT / "dist" / "index.html").resolve().as_uri()
    out = ROOT / "dist" / "og.png"
    subprocess.run(
        [exe, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--virtual-time-budget=6000",
         "--window-size=1200,630", f"--screenshot={out}", src],
        check=True, capture_output=True,
    )
    print(f"{out} {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
