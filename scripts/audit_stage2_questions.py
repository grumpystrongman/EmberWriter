"""Audit local question inventories without claiming human verification."""
import json
import re
import sys


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
    """Read inventory from stdin; never open an untrusted CLI-supplied path."""
    if len(sys.argv) != 1:
        raise SystemExit("Usage: pipe a local JSON inventory into audit_stage2_questions.py")
    inventory = json.load(sys.stdin)
    if not isinstance(inventory, list) or any(not isinstance(item, dict) for item in inventory):
        raise ValueError("Question inventory must be a JSON array of objects")
    print(json.dumps(audit(inventory), indent=2))


if __name__ == "__main__":
    main()
