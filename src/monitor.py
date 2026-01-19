"""
YouTube channel monitor using RSS feeds.

Checks for new video uploads and triggers the pipeline when detected.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
from datetime import datetime


RSS_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
STATE_FILE = Path(__file__).parent.parent / "state.json"


def fetch_rss(channel_id: str) -> str:
    """Fetch RSS feed for a YouTube channel."""
    url = RSS_URL_TEMPLATE.format(channel_id=channel_id)
    try:
        with urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8")
    except URLError as e:
        raise RuntimeError(f"Failed to fetch RSS feed: {e}")


def parse_feed(xml_content: str) -> list[dict]:
    """
    Parse RSS feed and extract video information.

    Returns list of videos, newest first.
    """
    root = ET.fromstring(xml_content)

    # YouTube RSS uses Atom namespace
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/"
    }

    videos = []
    for entry in root.findall("atom:entry", ns):
        video_id = entry.find("yt:videoId", ns)
        title = entry.find("atom:title", ns)
        published = entry.find("atom:published", ns)

        if video_id is not None:
            videos.append({
                "video_id": video_id.text,
                "title": title.text if title is not None else "Unknown",
                "published": published.text if published is not None else None,
                "url": f"https://www.youtube.com/watch?v={video_id.text}"
            })

    return videos


def load_state() -> dict:
    """Load the state file containing last processed video."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_video_id": None, "last_check": None}


def save_state(state: dict) -> None:
    """Save the state file."""
    state["last_check"] = datetime.utcnow().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def check_for_new_videos(channel_id: str) -> list[dict]:
    """
    Check for new videos since last check.

    Returns list of new videos (may be empty).
    """
    state = load_state()
    last_video_id = state.get("last_video_id")

    xml_content = fetch_rss(channel_id)
    videos = parse_feed(xml_content)

    if not videos:
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
        sys.exit(1)

    print(f"Checking channel: {channel_id}")

    new_videos = check_for_new_videos(channel_id)

    if new_videos:
        print(f"\nFound {len(new_videos)} new video(s):")
        for video in new_videos:
            print(f"  - {video['title']}")
            print(f"    {video['url']}")

        # Output the newest video URL for pipeline
        # (In GitHub Actions, we'll capture this)
        print(f"\n::set-output name=new_video::true")
        print(f"::set-output name=video_url::{new_videos[0]['url']}")
        print(f"::set-output name=video_id::{new_videos[0]['video_id']}")
    else:
        print("No new videos found.")
        print(f"::set-output name=new_video::false")
