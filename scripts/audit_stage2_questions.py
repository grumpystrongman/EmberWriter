"""Audit local question inventories without claiming human verification."""
import argparse
import json
import re
from pathlib import Path


def audit(items):
    seen = set()
    duplicates = []
    reviewed = 0
    for index, item in enumerate(items, 1):
        question = item.get("question", "")
        if not isinstance(question, str):
            raise ValueError(f"Invalid question at row {index}")
        key = re.sub(r"\W+", " ", question.casefold()).strip()
        if not key:
            raise ValueError(f"Invalid question at row {index}")
        if key in seen:
            duplicates.append(index)
            continue
        seen.add(key)
        reference = item.get("review_reference")
        if item.get("origin") == "author_reviewed" and isinstance(reference, str) and reference.strip():
            reviewed += 1
    return {"total": len(items), "distinct_text": len(seen), "duplicate_rows": duplicates,
            "claimed_reviewed_distinct": reviewed, "target": 50,
            "human_review_independently_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(args.inventory.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
