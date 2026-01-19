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

from monitor import fetch_latest_videos, sanitize_filename
from transcribe import transcribe, segments_to_text
from segment import segment_transcript, extract_sermon_segments, segments_to_text as sermon_to_text
from cleanup import cleanup_sermon


OUTPUT_DIR = Path(__file__).parent.parent / "output"
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")
GPT_MODEL = os.environ.get("GPT_MODEL", "gpt-4o-mini")


def get_existing_sermons() -> set[str]:
    """Get set of video IDs that already have transcripts."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    existing = set()
    for f in OUTPUT_DIR.glob("sermon_*.txt"):
        # Try to extract video ID from filename or content
        # For now, we'll track by date+title pattern
        existing.add(f.stem)

    return existing


def filename_for_video(video: dict) -> str:
    """Generate the expected filename for a video."""
    date = video.get("upload_date", "")
    title = video.get("safe_title", sanitize_filename(video.get("title", "")))

    if date and date != "NA":
        return f"sermon_{date}_{title}"
    else:
        return f"sermon_{title}"


def video_has_transcript(video: dict) -> bool:
    """Check if a video already has a transcript file."""
    expected = filename_for_video(video)

    # Check for exact match or partial match (in case of naming variations)
    for f in OUTPUT_DIR.glob("sermon_*.txt"):
        # Match by video ID in filename or by date+title
        if video["video_id"] in f.stem or expected in f.stem:
            return True
        # Also check if the date and a significant part of title match
        if video.get("upload_date") and video["upload_date"] in f.stem:
            if video.get("safe_title", "")[:20] in f.stem:
                return True

    return False


def download_audio(url: str, output_path: Path) -> bool:
    """Download audio from YouTube video."""
    print(f"  Downloading audio...")
    try:
        result = subprocess.run(
            [
                "yt-dlp",
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

    # Paths
    audio_path = OUTPUT_DIR / "audio.mp3"
    transcript_path = OUTPUT_DIR / "audio_transcript.json"

    # 1. Download audio
    if not download_audio(url, audio_path.with_suffix(".%(ext)s")):
        return False

    # Find the actual downloaded file (might have different extension initially)
    audio_file = OUTPUT_DIR / "audio.mp3"
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
        boundaries = segment_transcript(formatted, model=GPT_MODEL)

        if not boundaries.get("sermon_start") or not boundaries.get("sermon_end"):
            print(f"  No sermon found: {boundaries.get('reasoning', 'Unknown reason')}")
            return False

        sermon_segments = extract_sermon_segments(
            result["segments"],
            boundaries["sermon_start"],
            boundaries["sermon_end"]
        )
        sermon_text = sermon_to_text(sermon_segments)
        print(f"  Found sermon: {boundaries['sermon_start']} - {boundaries['sermon_end']}")
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

    # Cleanup temp files
    audio_file.unlink(missing_ok=True)
    transcript_path.unlink(missing_ok=True)
    (OUTPUT_DIR / "audio_sermon.json").unlink(missing_ok=True)

    return True


def git_push(files: list[Path], message: str) -> bool:
    """Commit and push files to git."""
    try:
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

        # Commit
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True
        )

        # Push
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

    def extract_date_from_title(title: str) -> str | None:
        """Try to extract date from title."""
        # Match "Jan. 18, 2026" or "Dec. 28, 2025" format
        match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})', title)
        if match:
            month_map = {'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                         'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                         'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'}
            month = month_map[match.group(1)]
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
    to_process = []

    for video in recent_videos:
        title = video.get("title", "")

        # Skip daily/morning videos (e.g., daily devotionals, morning prayer)
        if "Daily" in title or "Morning" in title:
            print(f"  [SKIP] {title[:50]}... (daily/morning video)")
            continue

        if video_has_transcript(video):
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
    for video in to_process:
        success = process_video(video)
        if success:
            filename = filename_for_video(video)
            processed_files.append(OUTPUT_DIR / f"{filename}.txt")

    print(f"\n{'='*60}")
    print(f"Processed {len(processed_files)} of {len(to_process)} videos")

    # Push if requested
    if args.push and processed_files:
        print("\nPushing to GitHub...")
        message = f"Add {len(processed_files)} sermon transcript(s)"
        git_push(processed_files, message)


if __name__ == "__main__":
    main()
