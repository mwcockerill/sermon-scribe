"""
Backfill author field in published Jekyll sermon posts.

Scans all sermons in docs/_sermons/, finds those missing an author,
looks up the date in the Google Sheet, and patches the front matter.

Usage:
    python src/backfill_authors.py [--dry-run]
"""

import argparse
import re
from pathlib import Path

from authors import fetch_authors

JEKYLL_DIR = Path(__file__).parent.parent / "docs" / "_sermons"
FRONT_MATTER_RE = re.compile(r"^---\n(.*?\n)---\n", re.DOTALL)


def parse_front_matter(text: str) -> dict:
    """Extract key/value pairs from Jekyll front matter."""
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"')
    return fields


def patch_author(path: Path, author: str, dry_run: bool) -> bool:
    """Insert author field into the front matter of a sermon file."""
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        print(f"  SKIP {path.name}: could not parse front matter")
        return False

    fm_body = match.group(1)
    # Insert author line before closing ---
    new_fm_body = fm_body.rstrip("\n") + f'\nauthor: "{author}"\n'
    new_text = f"---\n{new_fm_body}---\n" + text[match.end():]

    if dry_run:
        print(f"  [DRY RUN] Would add author '{author}' to {path.name}")
    else:
        path.write_text(new_text, encoding="utf-8")
        print(f"  Patched: {path.name} → {author}")

    return True


def main():
    parser = argparse.ArgumentParser(description="Backfill missing authors in published sermons")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = parser.parse_args()

    print("Fetching authors sheet...")
    authors = fetch_authors()
    if not authors:
        print("No authors found in sheet — nothing to do.")
        return

    print(f"Found {len(authors)} author(s) in sheet")

    sermon_files = sorted(JEKYLL_DIR.glob("*.md"))
    patched = 0
    skipped_no_match = 0
    skipped_has_author = 0

    for path in sermon_files:
        text = path.read_text(encoding="utf-8")
        fields = parse_front_matter(text)

        if not fields:
            continue

        # Skip if author already present
        if fields.get("author"):
            skipped_has_author += 1
            continue

        date = fields.get("date")
        if not date:
            print(f"  SKIP {path.name}: no date in front matter")
            continue

        author = authors.get(date)
        if not author:
            skipped_no_match += 1
            continue

        if patch_author(path, author, dry_run=args.dry_run):
            patched += 1

    print(f"\nDone: {patched} patched, {skipped_has_author} already had author, {skipped_no_match} not in sheet")


if __name__ == "__main__":
    main()
