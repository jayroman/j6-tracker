"""
Check news sources for updates on J6 pardonees.

Uses NewsAPI (https://newsapi.org) to search for recent articles
mentioning tracked individuals alongside arrest/charge keywords.

Requires NEWSAPI_KEY environment variable.

Optional: Set ANTHROPIC_API_KEY to use Claude for article classification.
"""

import json
import sys
import os
import time
import logging
from pathlib import Path
from datetime import date, timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote
from urllib.error import URLError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "pardonees.json"
NEWSAPI_URL = "https://newsapi.org/v2/everything"
RATE_LIMIT_SECONDS = 1

# Keywords that suggest a status change
STATUS_KEYWORDS = [
    "arrested", "charged", "indicted", "sentenced",
    "jail", "prison", "custody", "detained",
    "mugshot", "booking", "arraigned",
]


def load_data() -> list[dict]:
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(records: list[dict]):
    with open(DATA_FILE, "w") as f:
        json.dump(records, f, indent=2)


def search_news(person_name: str, api_key: str, days_back: int = 7) -> list[dict]:
    """Search NewsAPI for recent articles about a person + arrest keywords."""
    from_date = (date.today() - timedelta(days=days_back)).isoformat()
    keyword_clause = " OR ".join(STATUS_KEYWORDS[:5])  # API has query length limits
    query = f'"{person_name}" AND ({keyword_clause})'

    params = {
        "q": query,
        "from": from_date,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 5,
        "apiKey": api_key,
    }

    url = f"{NEWSAPI_URL}?{urlencode(params, quote_via=quote)}"
    req = Request(url, headers={"User-Agent": "J6TrackerBot/1.0"})

    try:
        with urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            return result.get("articles", [])
    except (URLError, json.JSONDecodeError) as e:
        log.warning("News search failed for %s: %s", person_name, e)
        return []


def classify_article_simple(title: str, description: str) -> dict:
    """
    Simple keyword-based classification of whether an article indicates
    a re-arrest or new charges. Returns dict with 'is_relevant' and 'reason'.
    """
    text = f"{title} {description}".lower()

    arrest_signals = ["arrested", "charged", "indicted", "booked", "detained", "custody"]
    if any(kw in text for kw in arrest_signals):
        return {"is_relevant": True, "reason": "Article mentions arrest/charges"}

    return {"is_relevant": False, "reason": "No strong arrest signals"}


def classify_article_llm(title: str, description: str, person_name: str) -> dict:
    """
    Use Claude API to classify whether an article indicates a genuine
    re-arrest or new criminal charges for the named person.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return classify_article_simple(title, description)

    prompt = f"""Analyze this news article about {person_name}, a January 6 pardonee.

Title: {title}
Description: {description}

Does this article indicate that {person_name} has been:
1. Arrested on new charges (not related to the original Jan 6 case)
2. Currently incarcerated or in custody
3. Involved in new criminal activity

Respond with JSON only:
{{"is_relevant": true/false, "new_status": "re_arrested"|"incarcerated"|null, "charge": "description of new charge or null", "reason": "one sentence explanation"}}"""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            text = body["content"][0]["text"]
            # Extract JSON from response
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
    except Exception as e:
        log.warning("LLM classification failed: %s", e)
        return classify_article_simple(title, description)


def check_all():
    api_key = os.environ.get("NEWSAPI_KEY")
    if not api_key:
        log.error("NEWSAPI_KEY environment variable not set")
        sys.exit(1)

    records = load_data()
    changes = []
    flagged_articles = []
    today = date.today().isoformat()

    for record in records:
        name = record["name"]
        log.info("Searching news for %s...", name)

        articles = search_news(name, api_key)

        for article in articles:
            title = article.get("title", "")
            desc = article.get("description", "")
            url = article.get("url", "")
            pub_date = (article.get("publishedAt") or "")[:10]

            classification = classify_article_llm(title, desc, name)

            if classification.get("is_relevant"):
                flagged_articles.append({
                    "person": name,
                    "title": title,
                    "url": url,
                    "date": pub_date,
                    "classification": classification,
                })

                new_status = classification.get("new_status")
                new_charge = classification.get("charge")

                if new_status and record["current_status"] == "free":
                    record["current_status"] = new_status
                    record["current_status_detail"] = classification.get("reason", "")
                    record["re_arrested"] = True
                    record["re_arrest_date"] = pub_date
                    if new_charge:
                        record["re_arrest_charge"] = new_charge

                    # Add source
                    record.setdefault("sources", []).append({
                        "title": title,
                        "url": url,
                        "date": pub_date,
                    })

                    changes.append(f"{name}: free -> {new_status} ({new_charge or 'unknown charge'})")
                    log.info("STATUS CHANGE: %s", changes[-1])

        record["last_checked"] = today
        time.sleep(RATE_LIMIT_SECONDS)

    save_data(records)

    # Write flagged articles report
    if flagged_articles:
        report_path = Path(__file__).resolve().parent.parent / "data" / "flagged_articles.json"
        with open(report_path, "w") as f:
            json.dump(flagged_articles, f, indent=2)
        log.info("Wrote %d flagged articles to %s", len(flagged_articles), report_path)

    if changes:
        log.info("=== %d status change(s) detected ===", len(changes))
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a") as f:
                f.write("## News Status Changes\n")
                for c in changes:
                    f.write(f"- {c}\n")
    else:
        log.info("No status changes from news.")

    return changes


if __name__ == "__main__":
    check_all()
