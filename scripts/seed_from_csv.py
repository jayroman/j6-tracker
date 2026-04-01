"""
Seed or expand the pardonees database from a CSV file.

Usage:
  python scripts/seed_from_csv.py input.csv

Expected CSV columns (flexible, will map common variations):
  name, state, charge, sentence, pardon_date

This merges with existing data — it won't overwrite records that already exist
(matched by normalized name).
"""

import csv
import json
import re
import sys
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "pardonees.json"


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def name_to_id(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return f"{parts[-1].lower()}-{parts[0].lower()}"
    return re.sub(r"[^a-z0-9]", "-", name.lower())


def load_existing() -> list[dict]:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def save_data(records: list[dict]):
    with open(DATA_FILE, "w") as f:
        json.dump(records, f, indent=2)


# Map common CSV header variations to our field names
COLUMN_MAP = {
    "name": "name",
    "full_name": "name",
    "defendant": "name",
    "state": "state",
    "st": "state",
    "charge": "original_charge",
    "charges": "original_charge",
    "original_charge": "original_charge",
    "sentence": "original_sentence",
    "original_sentence": "original_sentence",
    "pardon_date": "pardon_date",
    "date": "pardon_date",
}


def map_columns(header: list[str]) -> dict[int, str]:
    mapping = {}
    for i, col in enumerate(header):
        normalized = col.strip().lower().replace(" ", "_")
        if normalized in COLUMN_MAP:
            mapping[i] = COLUMN_MAP[normalized]
    return mapping


def main():
    if len(sys.argv) < 2:
        print("Usage: python seed_from_csv.py <input.csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    existing = load_existing()
    existing_names = {normalize_name(r["name"]) for r in existing}

    added = 0
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        col_map = map_columns(header)

        if not col_map:
            print(f"Could not map any columns. Header: {header}")
            sys.exit(1)

        print(f"Mapped columns: {col_map}")

        for row in reader:
            record_data = {}
            for i, field_name in col_map.items():
                if i < len(row):
                    record_data[field_name] = row[i].strip()

            name = record_data.get("name", "").strip()
            if not name:
                continue

            if normalize_name(name) in existing_names:
                continue

            new_record = {
                "id": name_to_id(name),
                "name": name,
                "age": None,
                "state": record_data.get("state", ""),
                "original_charge": record_data.get("original_charge", ""),
                "original_sentence": record_data.get("original_sentence", ""),
                "pardon_date": record_data.get("pardon_date", "2025-01-20"),
                "current_status": "free",
                "current_status_detail": "Released after pardon",
                "re_arrested": False,
                "re_arrest_date": None,
                "re_arrest_charge": None,
                "sources": [],
                "last_checked": None,
                "notes": "",
            }

            existing.append(new_record)
            existing_names.add(normalize_name(name))
            added += 1

    save_data(existing)
    print(f"Added {added} new records. Total: {len(existing)}")


if __name__ == "__main__":
    main()
