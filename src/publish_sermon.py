#!/usr/bin/env python3
"""
Convert sermon transcript to Jekyll markdown format and save to docs/_sermons/
"""

import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path


STATE_FILE = Path(__file__).parent.parent / "state.json"


def update_state(video_id, date, state_file=None):
    """
    Advance state.json to the sermon we just published.

    The monitor uses last_video_id as a stop marker when walking the channel
    listing, so it must only ever move forward. Backfilling an older service
    (or publishing with a date the Makefile couldn't parse) leaves it alone --
    rewinding the marker would make the monitor re-report everything newer.

    Returns True if the state was advanced, False if it was left as-is.
    """
    state_file = Path(state_file) if state_file else STATE_FILE

    if not date:
        print("No date for this sermon - leaving state.json unchanged")
        return False

    state = {}
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)

    last_published = state.get("last_published_date")
    if last_published and date <= last_published:
        print(f"state.json already at {last_published} - not rewinding to {date}")
        return False

    state["last_video_id"] = video_id
    state["last_published_date"] = date
    state["last_check"] = datetime.now(timezone.utc).isoformat()

    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

    print(f"Updated state.json: last_video_id={video_id} ({date})")
    return True


def sanitize_filename(text):
    """Convert text to lowercase and replace spaces with underscores for filename"""
    return text.lower().replace(' ', '_').replace(',', '')


def extract_description(text, max_length=200):
    """Extract first ~200 characters for description"""
    # Remove extra whitespace and newlines
    clean_text = ' '.join(text.split())
    if len(clean_text) <= max_length:
        return clean_text
    # Cut at word boundary
    truncated = clean_text[:max_length].rsplit(' ', 1)[0]
    return truncated + "..."


def create_jekyll_sermon(sermon_text, title, date, video_id, output_dir):
    """
    Create Jekyll-formatted markdown file

    Args:
        sermon_text: Full sermon transcript text
        title: Sermon title (e.g., "Jan. 18, 2026 | Confession of St. Peter")
        date: Date in YYYY-MM-DD format
        video_id: YouTube video ID
        output_dir: Directory to save the markdown file (docs/_sermons/)
    """
    # Create description from first part of sermon
    description = extract_description(sermon_text)

    # Create Jekyll front matter
    front_matter = f"""---
title: "{title}"
date: {date}
youtube_id: "{video_id}"
description: "{description}"
---

"""

    # Combine front matter with sermon text
    full_content = front_matter + sermon_text

    # Create filename: YYYY-MM-DD-title.md
    # Extract just the title part after the date if present
    title_part = title
    if '|' in title:
        title_part = title.split('|', 1)[1].strip()
    elif '–' in title or '—' in title:
        title_part = title.split('–', 1)[1].strip() if '–' in title else title.split('—', 1)[1].strip()

    sanitized_title = sanitize_filename(title_part)
    filename = f"{date}-{sanitized_title}.md"

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Write the file
    output_path = os.path.join(output_dir, filename)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_content)

    print(f"Created Jekyll sermon: {output_path}")
    return output_path


def main():
    if len(sys.argv) != 5:
        print("Usage: python publish_sermon.py <sermon_txt_file> <title> <date> <video_id>")
        print("  sermon_txt_file: Path to the sermon transcript (e.g., output/sermon_2026-01-18_Title.txt)")
        print("  title: Full title (e.g., 'Jan. 18, 2026 | Confession of St. Peter')")
        print("  date: Date in YYYY-MM-DD format")
        print("  video_id: YouTube video ID")
        sys.exit(1)

    sermon_file = sys.argv[1]
    title = sys.argv[2]
    date = sys.argv[3]
    video_id = sys.argv[4]

    # Read sermon text
    if not os.path.exists(sermon_file):
        print(f"Error: Sermon file not found: {sermon_file}")
        sys.exit(1)

    with open(sermon_file, 'r', encoding='utf-8') as f:
        sermon_text = f.read().strip()

    # Output directory for Jekyll sermons
    output_dir = "docs/_sermons"

    # Create Jekyll sermon
    create_jekyll_sermon(sermon_text, title, date, video_id, output_dir)

    # Record what we published so the monitor doesn't re-report it
    update_state(video_id, date)


if __name__ == "__main__":
    main()
