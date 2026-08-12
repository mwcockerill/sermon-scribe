"""Tests for state.json bookkeeping in publish_sermon."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import publish_sermon


def read_state(state_file):
    return json.loads(state_file.read_text())


def test_publishing_advances_state_to_the_published_video(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({
        "last_video_id": "V6v2EG9Ncy8",
        "last_published_date": "2026-07-26",
        "last_check": "2026-08-05T01:43:10+00:00",
    }))

    updated = publish_sermon.update_state("nrw15bI8Emw", "2026-08-02", state_file=state_file)

    assert updated is True
    state = read_state(state_file)
    assert state["last_video_id"] == "nrw15bI8Emw"
    assert state["last_published_date"] == "2026-08-02"


def test_publishing_an_older_sermon_does_not_move_the_marker_backwards(tmp_path):
    """Backfilling an old service must not rewind the monitor's marker."""
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({
        "last_video_id": "nrw15bI8Emw",
        "last_published_date": "2026-08-02",
    }))

    updated = publish_sermon.update_state("k1iMGvGjxfI", "2026-07-12", state_file=state_file)

    assert updated is False
    state = read_state(state_file)
    assert state["last_video_id"] == "nrw15bI8Emw"
    assert state["last_published_date"] == "2026-08-02"


def test_missing_date_leaves_state_untouched(tmp_path):
    """The Makefile passes an empty date when it can't parse one from the title."""
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({
        "last_video_id": "nrw15bI8Emw",
        "last_published_date": "2026-08-02",
    }))

    updated = publish_sermon.update_state("someVideo", "", state_file=state_file)

    assert updated is False
    assert read_state(state_file)["last_video_id"] == "nrw15bI8Emw"


def test_state_file_is_created_when_absent(tmp_path):
    state_file = tmp_path / "state.json"

    updated = publish_sermon.update_state("nrw15bI8Emw", "2026-08-02", state_file=state_file)

    assert updated is True
    assert read_state(state_file)["last_video_id"] == "nrw15bI8Emw"


def test_unrelated_state_keys_are_preserved(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({
        "last_video_id": "old",
        "last_published_date": "2026-07-26",
        "last_check": "2026-08-05T01:43:10+00:00",
    }))

    publish_sermon.update_state("nrw15bI8Emw", "2026-08-02", state_file=state_file)

    assert "last_check" in read_state(state_file)


def test_main_updates_state_after_publishing(tmp_path, monkeypatch):
    sermon_file = tmp_path / "sermon.txt"
    sermon_file.write_text("Life is hard, and God makes all things work together for good.")
    state_file = tmp_path / "state.json"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(publish_sermon, "STATE_FILE", state_file)
    monkeypatch.setattr(sys, "argv", [
        "publish_sermon.py",
        str(sermon_file),
        "Aug. 2, 2026 | Pentecost 10",
        "2026-08-02",
        "nrw15bI8Emw",
    ])

    publish_sermon.main()

    assert (tmp_path / "docs" / "_sermons" / "2026-08-02-pentecost_10.md").exists()
    assert read_state(state_file)["last_video_id"] == "nrw15bI8Emw"
