"""
Build script: copies site files + data into a dist/ folder ready for deployment.

For GitHub Pages or any static hosting — the output is a self-contained
directory with no build tools required.
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
DATA_DIR = ROOT / "data"
DIST_DIR = ROOT / "dist"


def build():
    # Clean
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)

    # Copy site files
    shutil.copytree(SITE_DIR, DIST_DIR)

    # Copy data into dist
    dist_data = DIST_DIR / "data"
    dist_data.mkdir(exist_ok=True)
    shutil.copy2(DATA_DIR / "pardonees.json", dist_data / "pardonees.json")

    # Update the fetch path in app.js to work from dist/
    app_js = DIST_DIR / "app.js"
    content = app_js.read_text()
    content = content.replace("../data/pardonees.json", "data/pardonees.json")
    app_js.write_text(content)

    print(f"Built site to {DIST_DIR}")
    print(f"  Files: {list(DIST_DIR.rglob('*'))}")


if __name__ == "__main__":
    build()
