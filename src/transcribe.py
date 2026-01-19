"""
Transcription module using OpenAI Whisper.

Transcribes audio/video files and returns timestamped segments
for downstream processing (segmentation, cleanup).
"""

import torch
import whisper
from pathlib import Path


def get_device() -> str:
    """Get the best available device for Whisper."""
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def transcribe(
    audio_path: str,
    model_name: str = "base",
    language: str = "en"
) -> dict:
    """
    Transcribe an audio file using Whisper.

    Args:
        audio_path: Path to the audio/video file
        model_name: Whisper model size (tiny, base, small, medium, large)
        language: Language code (e.g., 'en' for English)

    Returns:
        dict with keys:
            - text: Full transcript as a single string
            - segments: List of segments with timestamps
              Each segment has: start, end, text
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    device = get_device()
    print(f"Loading Whisper model: {model_name} (device: {device})")
    model = whisper.load_model(model_name, device=device)

    print(f"Transcribing: {audio_path.name}")
    result = model.transcribe(
        str(audio_path),
        language=language,
        verbose=False
    )

    # Extract relevant data
    segments = [
        {
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip()
        }
        for seg in result["segments"]
    ]

    return {
        "text": result["text"].strip(),
        "segments": segments,
        "language": result.get("language", language)
    }


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def segments_to_text(segments: list, include_timestamps: bool = True) -> str:
    """
    Convert segments to readable text format.

    Args:
        segments: List of segment dicts with start, end, text
        include_timestamps: Whether to include timestamps in output

    Returns:
        Formatted transcript string
    """
    lines = []
    for seg in segments:
        if include_timestamps:
            timestamp = format_timestamp(seg["start"])
            lines.append(f"[{timestamp}] {seg['text']}")
        else:
            lines.append(seg["text"])

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <audio_file> [model_name]")
        print("Models: tiny, base, small, medium, large")
        sys.exit(1)

    audio_file = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "base"

    result = transcribe(audio_file, model_name=model)

    print("\n" + "=" * 60)
    print("TRANSCRIPT")
    print("=" * 60)
    print(segments_to_text(result["segments"]))

    # Save JSON output
    output_path = Path(audio_file).stem + "_transcript.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nFull transcript saved to: {output_path}")
