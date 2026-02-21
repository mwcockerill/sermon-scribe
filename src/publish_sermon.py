#!/usr/bin/env python3
"""
Convert sermon transcript to Jekyll markdown format and save to docs/_sermons/
"""

import sys
import os


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


if __name__ == "__main__":
    main()
