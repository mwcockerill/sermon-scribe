"""Tests for state.json bookkeeping in the batch (catch-up) pipeline.

The expensive, external stages -- yt-dlp, Whisper, the OpenAI calls -- are
stubbed. Everything downstream of them (the Jekyll post, the state write) runs
for real against tmp_path, because that wiring is what these tests are about.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import process_recent
import publish_sermon


VIDEO = {
    "video_id": "o3tIMvxdsV8",
    "title": "Aug. 9, 2026 | Pentecost 11",
    "safe_title": "Aug._9,_2026_Pentecost_11",
    "url": "https://www.youtube.com/watch?v=o3tIMvxdsV8",
    "upload_date": "2026-08-09",
}

TRANSCRIPT = {"segments": [{"start": 0.0, "end": 1500.0, "text": "a sermon about boats"}]}


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    """Stub the external stages and point all output at tmp_path."""
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(process_recent, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(process_recent, "JEKYLL_DIR", tmp_path / "docs" / "_sermons")
    monkeypatch.setattr(publish_sermon, "STATE_FILE", state_file)
    (tmp_path / "output").mkdir()

    def fake_download(url, output_path):
        (tmp_path / "output" / f"audio_{VIDEO['video_id']}.mp3").write_bytes(b"audio")
        return True

    monkeypatch.setattr(process_recent, "download_audio", fake_download)
    monkeypatch.setattr(process_recent, "transcribe", lambda *a, **k: TRANSCRIPT)
    monkeypatch.setattr(process_recent, "segments_to_text", lambda *a, **k: "text")
    monkeypatch.setattr(process_recent, "segment_transcript", lambda *a, **k: {
        "sermon_start": "00:05:00",
        "sermon_end": "00:25:00",
        "confidence": "high",
        "reasoning": "extended teaching",
    })
    monkeypatch.setattr(process_recent, "extract_sermon_segments", lambda *a, **k: TRANSCRIPT["segments"])
    monkeypatch.setattr(process_recent, "flatten_segments", lambda *a, **k: "raw sermon text")
    monkeypatch.setattr(process_recent, "cleanup_sermon", lambda *a, **k: "Cleaned sermon text.")
    monkeypatch.setattr(process_recent, "lookup_author", lambda *a, **k: None)
    monkeypatch.setattr(process_recent, "fetch_video_date", lambda vid: "2026-08-09")

    return state_file


def read_state(state_file):
    return json.loads(state_file.read_text())


def test_processing_a_video_advances_state(pipeline):
    assert process_recent.process_video(dict(VIDEO)) is True

    state = read_state(pipeline)
    assert state["last_video_id"] == "o3tIMvxdsV8"
    assert state["last_published_date"] == "2026-08-09"


def test_state_uses_the_resolved_service_date_not_the_listing_date(pipeline, monkeypatch):
    """resolve_service_date trusts the aired date over the title; state must match."""
    monkeypatch.setattr(process_recent, "fetch_video_date", lambda vid: "2026-08-10")

    process_recent.process_video(dict(VIDEO))

    assert read_state(pipeline)["last_published_date"] == "2026-08-10"


def test_no_sermon_found_leaves_state_untouched(pipeline, monkeypatch):
    """A video with no sermon writes a placeholder -- it was never published."""
    monkeypatch.setattr(process_recent, "segment_transcript", lambda *a, **k: {
        "reasoning": "no extended teaching found",
    })

    assert process_recent.process_video(dict(VIDEO)) is False
    assert not pipeline.exists()


def test_batch_ends_at_the_newest_sermon_regardless_of_order(pipeline, monkeypatch):
    """Videos arrive newest-first, so an older one must not claw the marker back."""
    older = dict(VIDEO, video_id="k1iMGvGjxfI", title="July 12, 2026 | Pentecost 7",
                 safe_title="July_12,_2026_Pentecost_7")

    monkeypatch.setattr(process_recent, "fetch_video_date", lambda vid: "2026-08-09")
    process_recent.process_video(dict(VIDEO))

    def fake_download_older(url, output_path):
        (pipeline.parent / "output" / f"audio_{older['video_id']}.mp3").write_bytes(b"audio")
        return True

    monkeypatch.setattr(process_recent, "download_audio", fake_download_older)
    monkeypatch.setattr(process_recent, "fetch_video_date", lambda vid: "2026-07-12")
    process_recent.process_video(older)

    state = read_state(pipeline)
    assert state["last_video_id"] == "o3tIMvxdsV8"
    assert state["last_published_date"] == "2026-08-09"


def test_reuses_the_publish_sermon_guard(pipeline):
    """One no-rewind rule, not two copies of it."""
    assert process_recent.update_state is publish_sermon.update_state
