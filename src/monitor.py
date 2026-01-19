"""
YouTube channel monitor using yt-dlp.

Checks for new video uploads and triggers the pipeline when detected.
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone


STATE_FILE = Path(__file__).parent.parent / "state.json"


def fetch_latest_videos(channel_id: str, limit: int = 5) -> list[dict]:
    """
    Fetch latest videos from a YouTube channel using yt-dlp.

    Args:
        channel_id: YouTube channel ID (UCxxxx) or handle (@name)
        limit: Number of videos to fetch

    Returns:
        List of video dicts with id, title, url
    """
    # Support both channel ID and handle formats
    if channel_id.startswith("@"):
        channel_url = f"https://www.youtube.com/{channel_id}/videos"
    elif channel_id.startswith("UC"):
        channel_url = f"https://www.youtube.com/channel/{channel_id}/videos"
    else:
        channel_url = f"https://www.youtube.com/@{channel_id}/videos"

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--flat-playlist",
                "--print", "%(id)s\t%(title)s",
                "--playlist-end", str(limit),
                channel_url
            ],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed: {result.stderr}")

        videos = []
        for line in result.stdout.strip().split("\n"):
            if "\t" in line:
                video_id, title = line.split("\t", 1)
                videos.append({
                    "video_id": video_id,
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={video_id}"
                })

        return videos

    except subprocess.TimeoutExpired:
        raise RuntimeError("yt-dlp timed out fetching channel videos")
    except FileNotFoundError:
        raise RuntimeError("yt-dlp not found - please install it")


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

        # Output for GitHub Actions
        print(f"\n::set-output name=new_video::true")
        print(f"::set-output name=video_url::{new_videos[0]['url']}")
        print(f"::set-output name=video_id::{new_videos[0]['video_id']}")
    else:
        print("No new videos found.")
        print(f"::set-output name=new_video::false")
