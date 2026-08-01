"""
Process recent videos that don't have transcripts yet.

Usage:
    python src/process_recent.py [--days 7] [--dry-run] [--push]
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from monitor import fetch_latest_videos, sanitize_filename, is_video_available
from transcribe import transcribe, segments_to_text
from segment import segment_transcript, extract_sermon_segments, flatten_segments, timestamp_to_seconds
from cleanup import cleanup_sermon
from authors import fetch_authors, lookup_author


OUTPUT_DIR = Path(__file__).parent.parent / "output"
JEKYLL_DIR = Path(__file__).parent.parent / "docs" / "_sermons"
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "medium")
GPT_MODEL = os.environ.get("GPT_MODEL", "gpt-4o-mini")

MONTH_MAP = {
    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
}
# Accepts abbreviated and full month names: "Apr. 19, 2026", "July 29, 2026", "June 7 2026".
# The trailing [a-z]* is essential — without it "July" matches "Jul" and then fails on "y".
DATE_IN_TITLE_RE = re.compile(
    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})'
)


def extract_date_from_title(title: str) -> str | None:
    """Extract a YYYY-MM-DD date from a video title, or None if there isn't one."""
    match = DATE_IN_TITLE_RE.search(title)
    if match:
        month = MONTH_MAP[match.group(1)]
        day = match.group(2).zfill(2)
        year = match.group(3)
        return f"{year}-{month}-{day}"

    # Match YYYY MM DD pattern (Morning Prayer titles)
    match = re.search(r'(\d{4})\s+(\d{2})\s+(\d{2})', title)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    # Match YYYY-MM-DD pattern
    match = re.search(r'(\d{4}-\d{2}-\d{2})', title)
    if match:
        return match.group(1)

    return None


def resolve_service_date(video: dict, today: str | None = None) -> str:
    """
    Determine the date a service actually took place, as YYYY-MM-DD.

    Most reliable source first: the video's release_date (when a livestream aired),
    then the date in the title (the church's own label, occasionally mistyped), then
    today as a last resort — which is almost always wrong and says so loudly.

    `today` is injectable so the fallback branch is testable.
    """
    title = video.get("title", "")
    video_date = fetch_video_date(video.get("video_id", ""))
    title_date = extract_date_from_title(title)

    if video_date:
        if title_date and title_date != video_date:
            print(f"  NOTE: title says {title_date} but the video aired {video_date} — using {video_date}")
        return video_date

    if title_date:
        print(f"  WARNING: no date in video metadata — extracted from title: {title_date}")
        return title_date

    fallback = today or datetime.now().strftime("%Y-%m-%d")
    print(f"  WARNING: no date in metadata or title '{title}' — falling back to today ({fallback}).")
    print(f"  WARNING: this date is a guess and is probably wrong. Fix it before publishing.")
    return fallback


def fetch_video_date(video_id: str) -> str | None:
    """
    Fetch the authoritative date for a video as YYYY-MM-DD, or None if unavailable.

    Prefers release_date (when a livestream actually aired) over upload_date, which
    can be a day or more later. Requires a per-video lookup: --flat-playlist returns
    NA for both fields, so the channel listing cannot supply this.
    """
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--skip-download",
                "--print", "%(release_date)s\t%(upload_date)s",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return None

        parts = result.stdout.strip().split("\t")
        for value in parts:  # release_date first, then upload_date
            if value and value != "NA" and len(value) == 8 and value.isdigit():
                return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

    return None


def get_published_video_ids() -> set[str]:
    """Get set of video IDs that already have published Jekyll posts."""
    published = set()
    for f in JEKYLL_DIR.glob("*.md"):
        with open(f) as fh:
            in_front_matter = False
            for line in fh:
                stripped = line.strip()
                if stripped == "---":
                    if not in_front_matter:
                        in_front_matter = True
                        continue
                    else:
                        break  # End of front matter
                if in_front_matter and stripped.startswith("youtube_id:"):
                    vid = stripped.split(":", 1)[1].strip().strip('"')
                    if vid:
                        published.add(vid)
                    break
    return published


def generate_jekyll_post(video: dict, content: str, date_str: str, author: str | None = None) -> Path:
    """Generate a Jekyll-compatible markdown file for the sermon."""
    JEKYLL_DIR.mkdir(parents=True, exist_ok=True)

    title = video.get("title", "Untitled")
    video_id = video.get("video_id", "")
    safe_title = video.get("safe_title", sanitize_filename(title))

    # Jekyll filename format: YYYY-MM-DD-title.md
    jekyll_filename = f"{date_str}-{safe_title.lower()}.md"
    jekyll_path = JEKYLL_DIR / jekyll_filename

    # Get first paragraph as description (for social sharing)
    paragraphs = content.strip().split("\n\n")
    description = paragraphs[0][:200] + "..." if paragraphs else ""

    # Build front matter
    author_line = f'\nauthor: "{author}"' if author else ""
    front_matter = f"""---
title: "{title}"
date: {date_str}
youtube_id: "{video_id}"
description: "{description.replace('"', "'")}"{ author_line}
---

"""

    with open(jekyll_path, "w") as f:
        f.write(front_matter)
        f.write(content)

    return jekyll_path


def filename_for_video(video: dict) -> str:
    """Generate the expected filename for a video."""
    date = video.get("upload_date", "")
    title = video.get("safe_title", sanitize_filename(video.get("title", "")))

    if date and date != "NA":
        return f"sermon_{date}_{title}"
    else:
        return f"sermon_{title}"


def video_has_transcript(video: dict, published_ids: set[str], force: bool = False) -> bool:
    """Check if a video already has a published Jekyll post or placeholder."""
    # Primary check: video ID in published Jekyll posts (reliable, format-independent)
    if video["video_id"] in published_ids:
        return True

    # Check for a placeholder file (previous attempt found no sermon)
    expected = filename_for_video(video)
    placeholder = OUTPUT_DIR / f"{expected}.txt"
    if placeholder.exists() and placeholder.read_text().startswith("[NO SERMON FOUND]"):
        if force:
            print(f"  [FORCE] Removing placeholder to retry: {placeholder.name}")
            placeholder.unlink()
            return False
        return True

    return False


def download_audio(url: str, output_path: Path) -> bool:
    """Download audio from YouTube video."""
    print(f"  Downloading audio...")
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--extractor-args", "youtube:player_client=android",
                "-x",
                "--audio-format", "mp3",
                "-o", str(output_path),
                url
            ],
            capture_output=True,
            text=True,
            timeout=600
        )
        if result.returncode != 0:
            print(f"  Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"  Error downloading: {e}")
        return False


def process_video(video: dict) -> bool:
    """Process a single video through the full pipeline."""
    video_id = video["video_id"]
    title = video["title"]
    url = video["url"]

    print(f"\nProcessing: {title}")
    print(f"  URL: {url}")

    # Paths — scoped to this video_id to prevent cross-video contamination
    audio_path = OUTPUT_DIR / f"audio_{video_id}.mp3"
    transcript_path = OUTPUT_DIR / f"audio_{video_id}_transcript.json"

    # 1. Download audio
    if not download_audio(url, audio_path.with_suffix(".%(ext)s")):
        return False

    # Find the actual downloaded file (might have different extension initially)
    audio_file = OUTPUT_DIR / f"audio_{video_id}.mp3"
    if not audio_file.exists():
        print("  Error: Audio file not found after download")
        return False

    # 2. Transcribe
    print(f"  Transcribing with Whisper ({WHISPER_MODEL})...")
    try:
        result = transcribe(str(audio_file), model_name=WHISPER_MODEL)
        with open(transcript_path, "w") as f:
            json.dump(result, f, indent=2)
    except Exception as e:
        print(f"  Error transcribing: {e}")
        return False

    # 3. Segment
    print(f"  Segmenting with GPT ({GPT_MODEL})...")
    try:
        formatted = segments_to_text(result["segments"], include_timestamps=True)
        boundaries = segment_transcript(formatted, model=GPT_MODEL, title=title)

        if not boundaries.get("sermon_start") or not boundaries.get("sermon_end"):
            reason = boundaries.get('reasoning', 'Unknown reason')
            print(f"  No sermon found: {reason}")
            # Save placeholder file so we don't reprocess this video
            filename = filename_for_video(video)
            output_file = OUTPUT_DIR / f"{filename}.txt"
            with open(output_file, "w") as f:
                f.write(f"[NO SERMON FOUND]\n\n{reason}")
            print(f"  Saved placeholder: {output_file.name}")
            return False

        confidence = boundaries.get("confidence", "unknown")
        reasoning = boundaries.get("reasoning", "")
        print(f"  Found sermon: {boundaries['sermon_start']} - {boundaries['sermon_end']} (confidence: {confidence})")
        print(f"  Reasoning: {reasoning}")
        if confidence in ("low", "medium"):
            print(f"  WARNING: GPT confidence is '{confidence}' — review this transcript manually before publishing")

        # Validate sermon duration
        start_sec = timestamp_to_seconds(boundaries["sermon_start"])
        end_sec = timestamp_to_seconds(boundaries["sermon_end"])
        duration_min = (end_sec - start_sec) / 60
        if duration_min < 5:
            print(f"  WARNING: Sermon is only {duration_min:.1f} min — boundary may be wrong")
        elif duration_min > 60:
            print(f"  WARNING: Sermon is {duration_min:.1f} min — boundary may be too broad")

        sermon_segments = extract_sermon_segments(
            result["segments"],
            boundaries["sermon_start"],
            boundaries["sermon_end"]
        )
        sermon_text = flatten_segments(sermon_segments)
    except Exception as e:
        print(f"  Error segmenting: {e}")
        return False

    # 4. Cleanup
    print(f"  Cleaning up transcript...")
    try:
        cleaned = cleanup_sermon(sermon_text, model=GPT_MODEL)
    except Exception as e:
        print(f"  Error cleaning: {e}")
        return False

    # 5. Save output
    filename = filename_for_video(video)
    output_file = OUTPUT_DIR / f"{filename}.txt"

    with open(output_file, "w") as f:
        f.write(cleaned)

    print(f"  Saved: {output_file.name}")

    # 6. Generate Jekyll page
    upload_date = resolve_service_date(video)

    author = lookup_author(upload_date)
    if author:
        print(f"  Author: {author}")
    else:
        print(f"  Author: not found in sheet")

    jekyll_file = generate_jekyll_post(video, cleaned, upload_date, author=author)
    print(f"  Jekyll: {jekyll_file.name}")

    # Cleanup temp files
    audio_file.unlink(missing_ok=True)
    transcript_path.unlink(missing_ok=True)
    (OUTPUT_DIR / f"audio_{video_id}_sermon.json").unlink(missing_ok=True)

    return True


def git_push(files: list[Path], message: str) -> bool:
    """Commit and push files to git."""
    try:
        # Pull remote changes first so our staged files cleanly overwrite
        # any placeholders already on the remote (avoids add/add conflicts)
        subprocess.run(["git", "pull", "--rebase"], check=True)

        # Add files
        subprocess.run(["git", "add"] + [str(f) for f in files], check=True)

        # Check if there are changes
        result = subprocess.run(
            ["git", "diff", "--staged", "--quiet"],
            capture_output=True
        )

        if result.returncode == 0:
            print("No changes to commit")
            return True

        # Commit and push
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True
        )

        subprocess.run(["git", "push"], check=True)
        print("Pushed to GitHub")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Process recent videos without transcripts")
    parser.add_argument("--days", type=int, default=7, help="Look back this many days (default: 7)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without doing it")
    parser.add_argument("--push", action="store_true", help="Commit and push results to GitHub")
    parser.add_argument("--force", action="store_true", help="Retry videos that previously had no sermon found")
    parser.add_argument("--channel", type=str, help="YouTube channel ID (or set YOUTUBE_CHANNEL_ID env var)")
    args = parser.parse_args()

    # Get channel ID
    channel_id = args.channel or os.environ.get("YOUTUBE_CHANNEL_ID")
    if not channel_id:
        print("Error: No channel ID provided")
        print("Use --channel or set YOUTUBE_CHANNEL_ID environment variable")
        sys.exit(1)

    print(f"Checking channel: {channel_id}")
    print(f"Looking back: {args.days} days")

    # Fetch recent videos
    try:
        videos = fetch_latest_videos(channel_id, limit=20)
    except Exception as e:
        print(f"Error fetching videos: {e}")
        sys.exit(1)

    if not videos:
        print("No videos found")
        sys.exit(0)

    # Filter to videos within date range
    cutoff = datetime.now() - timedelta(days=args.days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    recent_videos = []
    for v in videos:
        upload_date = v.get("upload_date", "")

        # If upload_date is NA or empty, try to extract from title
        if not upload_date or upload_date == "NA":
            upload_date = extract_date_from_title(v.get("title", ""))

        if upload_date and upload_date >= cutoff_str:
            recent_videos.append(v)
        elif not upload_date:
            # Include if no date (can't filter)
            recent_videos.append(v)

    print(f"Found {len(recent_videos)} videos in the last {args.days} days")

    # Find videos without transcripts
    OUTPUT_DIR.mkdir(exist_ok=True)
    published_ids = get_published_video_ids()
    to_process = []

    for video in recent_videos:
        title = video.get("title", "")
        video_id = video.get("video_id", "")

        # Skip daily/morning videos (e.g., daily devotionals, morning prayer)
        if "Daily" in title or "Morning" in title:
            print(f"  [SKIP] {title[:50]}... (daily/morning video)")
            continue

        # Skip upcoming/unavailable videos
        if not is_video_available(video_id):
            print(f"  [SKIP] {title[:50]}... (upcoming/unavailable)")
            continue

        if video_has_transcript(video, published_ids, force=args.force):
            print(f"  [SKIP] {title[:50]}... (already has transcript)")
        else:
            print(f"  [NEW]  {title[:50]}...")
            to_process.append(video)

    if not to_process:
        print("\nAll recent videos already have transcripts!")
        sys.exit(0)

    print(f"\n{len(to_process)} video(s) need processing")

    if args.dry_run:
        print("\n[DRY RUN] Would process:")
        for v in to_process:
            print(f"  - {v['title']}")
        sys.exit(0)

    # Process each video
    processed_files = []
    placeholder_files = []
    for video in to_process:
        success = process_video(video)
        filename = filename_for_video(video)
        output_file = OUTPUT_DIR / f"{filename}.txt"
        if success:
            processed_files.append(output_file)
        elif output_file.exists():
            placeholder_files.append(output_file)

    print(f"\n{'='*60}")
    print(f"Processed {len(processed_files)} of {len(to_process)} videos")

    # Push if requested
    if args.push and (processed_files or placeholder_files):
        print("\nPushing to GitHub...")
        # Include both output/*.txt and docs/_sermons/*.md
        all_files = processed_files + placeholder_files + list(JEKYLL_DIR.glob("*.md"))
        parts = []
        if processed_files:
            parts.append(f"{len(processed_files)} sermon transcript(s)")
        if placeholder_files:
            parts.append(f"{len(placeholder_files)} placeholder(s)")
        message = f"Add {' and '.join(parts)}"
        git_push(all_files, message)


if __name__ == "__main__":
    main()
