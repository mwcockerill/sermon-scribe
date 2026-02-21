"""
YouTube channel monitor using yt-dlp.

Checks for new video uploads and triggers the pipeline when detected.
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone


STATE_FILE = Path(__file__).parent.parent / "state.json"


def sanitize_filename(title: str) -> str:
    """Convert title to safe filename format."""
    import re
    # Replace spaces with underscores
    safe = title.replace(" ", "_")
    # Remove or replace unsafe characters
    safe = re.sub(r'[<>:"/\\|?*]', '', safe)
    # Remove multiple underscores
    safe = re.sub(r'_+', '_', safe)
    # Remove leading/trailing underscores
    safe = safe.strip('_')
    # Limit length
    if len(safe) > 100:
        safe = safe[:100]
    return safe


def fetch_latest_videos(channel_id: str, limit: int = 5) -> list[dict]:
    """
    Fetch latest videos from a YouTube channel using yt-dlp.

    Checks both /videos and /streams tabs to get all content.

    Args:
        channel_id: YouTube channel ID (UCxxxx) or handle (@name)
        limit: Number of videos to fetch per tab

    Returns:
        List of video dicts with id, title, url
    """
    # Support both channel ID and handle formats
    if channel_id.startswith("@"):
        base_url = f"https://www.youtube.com/{channel_id}"
    elif channel_id.startswith("UC"):
        base_url = f"https://www.youtube.com/channel/{channel_id}"
    else:
        base_url = f"https://www.youtube.com/@{channel_id}"

    # Check both videos and streams tabs
    tabs = ["/videos", "/streams"]
    all_videos = {}  # Use dict to dedupe by video_id

    for tab in tabs:
        channel_url = base_url + tab
        try:
            result = subprocess.run(
                [
                    "yt-dlp",
                    "--flat-playlist",
                    "--print", "%(id)s\t%(title)s\t%(timestamp)s",
                    "--playlist-end", str(limit),
                    channel_url
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                print(f"Warning: Failed to fetch {tab}: {result.stderr}")
                continue

            for line in result.stdout.strip().split("\n"):
                if "\t" in line:
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        video_id, title, timestamp = parts[0], parts[1], parts[2]
                    else:
                        video_id, title, timestamp = parts[0], parts[1] if len(parts) > 1 else "", "NA"

                    # Skip if already seen
                    if video_id in all_videos:
                        continue

                    # Convert Unix timestamp to YYYY-MM-DD
                    # %(timestamp)s is reliably populated in flat-playlist; %(upload_date)s often returns NA
                    if timestamp and timestamp != "NA":
                        try:
                            formatted_date = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).strftime("%Y-%m-%d")
                        except (ValueError, OSError):
                            formatted_date = "NA"
                    else:
                        formatted_date = "NA"

                    # Sanitize title for filename
                    safe_title = sanitize_filename(title)

                    all_videos[video_id] = {
                        "video_id": video_id,
                        "title": title,
                        "safe_title": safe_title,
                        "upload_date": formatted_date,
                        "url": f"https://www.youtube.com/watch?v={video_id}"
                    }

        except subprocess.TimeoutExpired:
            print(f"Warning: Timeout fetching {tab}")
            continue
        except FileNotFoundError:
            raise RuntimeError("yt-dlp not found - please install it")

    return list(all_videos.values())


def is_video_available(video_id: str) -> bool:
    """
    Check if a video is available for download (not an upcoming live stream).

    Args:
        video_id: YouTube video ID

    Returns:
        True if video is available, False if upcoming/scheduled
    """
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--dump-json",
                "--skip-download",
                "--extractor-args", "youtube:player_client=android",
                f"https://www.youtube.com/watch?v={video_id}"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        # If yt-dlp fails, check if it's due to upcoming live stream
        if result.returncode != 0:
            if "live event will begin" in result.stderr:
                return False
            # Other errors - assume available and let download attempt fail if needed
            print(f"Warning: Could not verify availability for {video_id}: {result.stderr[:200]}")
            return True  # Try downloading anyway

        # Parse JSON to check live_status
        try:
            video_info = json.loads(result.stdout)
            live_status = video_info.get("live_status", "not_live")
            # Only process completed recordings; skip upcoming and active livestreams
            return live_status not in ("is_upcoming", "is_live")
        except json.JSONDecodeError:
            # If we can't parse, assume it's available
            return True

    except subprocess.TimeoutExpired:
        print(f"Warning: Timeout checking availability for {video_id}")
        return True  # Assume available, let download attempt
    except Exception as e:
        print(f"Warning: Error checking availability for {video_id}: {e}")
        return True  # Assume available, let download attempt


def load_state() -> dict:
    """Load the state file containing last processed video."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_video_id": None, "last_check": None}


def save_state(state: dict) -> None:
    """Save the state file."""
    state["last_check"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def check_for_new_videos(channel_id: str) -> list[dict]:
    """
    Check for new videos since last check.

    Returns list of new videos (may be empty).
    """
    state = load_state()
    last_video_id = state.get("last_video_id")

    videos = fetch_latest_videos(channel_id)

    if not videos:
        print("No videos found on channel")
        return []

    # If no previous state, just record the latest and return empty
    if last_video_id is None:
        state["last_video_id"] = videos[0]["video_id"]
        save_state(state)
        print(f"Initialized state with latest video: {videos[0]['title']}")
        return []

    # Find new videos (those before our last processed ID)
    new_videos = []
    for video in videos:
        if video["video_id"] == last_video_id:
            break

        # Skip daily/morning videos (e.g., daily devotionals, morning prayer)
        title = video.get("title", "")
        if "Daily" in title or "Morning" in title:
            print(f"Skipping daily/morning video: {title}")
            continue

        new_videos.append(video)

    return new_videos


def mark_processed(video_id: str) -> None:
    """Mark a video as processed."""
    state = load_state()
    state["last_video_id"] = video_id
    save_state(state)


if __name__ == "__main__":
    import sys
    import os

    # Get channel ID from args or environment
    if len(sys.argv) > 1:
        channel_id = sys.argv[1]
    else:
        channel_id = os.environ.get("YOUTUBE_CHANNEL_ID")

    if not channel_id:
        print("Usage: python monitor.py <channel_id>")
        print("Or set YOUTUBE_CHANNEL_ID environment variable")
        print("\nSupports: UC... channel IDs or @handle format")
        sys.exit(1)

    print(f"Checking channel: {channel_id}")

    new_videos = check_for_new_videos(channel_id)

    if new_videos:
        print(f"\nFound {len(new_videos)} new video(s):")
        for video in new_videos:
            print(f"  - {video['title']}")
            print(f"    {video['url']}")
    else:
        print("No new videos found.")
