"""
Check Bureau of Prisons inmate locator for custody status of pardonees.

BOP provides a public inmate search at:
  https://www.bop.gov/inmateloc/

This script queries their (unofficial) API endpoint to check if any
tracked individuals are currently in federal custody.
"""

import json
import sys
import os
import time
import logging
from pathlib import Path
from datetime import date
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import URLError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "pardonees.json"
BOP_SEARCH_URL = "https://www.bop.gov/PublicInfo/execute/inmateloc"

# Rate limit: be respectful, 2 seconds between requests
RATE_LIMIT_SECONDS = 2


def load_data() -> list[dict]:
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(records: list[dict]):
    with open(DATA_FILE, "w") as f:
        json.dump(records, f, indent=2)
    log.info("Data saved to %s", DATA_FILE)


def search_bop(last_name: str, first_name: str) -> dict | None:
    """
    Query BOP inmate locator. Returns inmate record dict if found, None otherwise.
    """
    params = {
        "nameFirst": first_name,
        "nameLast": last_name,
        "todo": "query",
        "output": "json",
    }
    url = f"{BOP_SEARCH_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "J6TrackerBot/1.0 (public interest research)"})

    try:
        with urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            inmates = result.get("InmateLocator", [])
            if inmates:
                return inmates[0]  # Return first match
    except (URLError, json.JSONDecodeError, KeyError) as e:
        log.warning("BOP lookup failed for %s %s: %s", first_name, last_name, e)

    return None


def check_all():
    records = load_data()
    changes = []
    today = date.today().isoformat()

    for record in records:
        name_parts = record["name"].split()
        if len(name_parts) < 2:
            continue

        first_name = name_parts[0]
        last_name = name_parts[-1]

        log.info("Checking BOP for %s %s...", first_name, last_name)
        result = search_bop(last_name, first_name)

        old_status = record["current_status"]

        if result:
            # Person found in BOP = currently in federal custody
            facility = result.get("fapiFacilityName", "Unknown facility")
            if old_status != "incarcerated":
                record["current_status"] = "incarcerated"
                record["current_status_detail"] = f"In federal custody at {facility}"
                changes.append(f"{record['name']}: {old_status} -> incarcerated ({facility})")
                log.info("STATUS CHANGE: %s is now incarcerated at %s", record["name"], facility)
        else:
            # Not in BOP — could be free, state custody, or name mismatch
            # Only update if they were previously marked incarcerated in federal system
            if old_status == "incarcerated" and "federal" in (record.get("current_status_detail") or "").lower():
                record["current_status"] = "free"
                record["current_status_detail"] = "No longer in BOP system"
                changes.append(f"{record['name']}: incarcerated -> free (not in BOP)")
                log.info("STATUS CHANGE: %s no longer in BOP", record["name"])

        record["last_checked"] = today
        time.sleep(RATE_LIMIT_SECONDS)

    save_data(records)

    if changes:
        log.info("=== %d status change(s) detected ===", len(changes))
        for c in changes:
            log.info("  %s", c)
        # Write changes summary for GitHub Actions to pick up
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a") as f:
                f.write("## BOP Status Changes\n")
                for c in changes:
                    f.write(f"- {c}\n")
    else:
        log.info("No status changes detected.")

    return changes


if __name__ == "__main__":
    changes = check_all()
    sys.exit(0)
