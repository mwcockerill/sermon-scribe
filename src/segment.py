"""
Segmentation module using OpenAI.

Analyzes a timestamped transcript to identify sermon boundaries
within a church service recording.
"""

import os
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")


SYSTEM_PROMPT = """You are an assistant that analyzes church service transcripts to identify the sermon portion.

A typical church service includes:
- Welcome/announcements
- Worship music/singing
- Prayer
- Scripture reading
- THE SERMON (main teaching - this is what we want to extract)
- Closing prayer
- Dismissal

The sermon is usually:
- The longest continuous section of teaching by one speaker
- Contains scripture references and exposition
- Has a teaching/preaching tone
- Usually 20-45 minutes long

Analyze the provided transcript and identify where the sermon begins and ends.
Return your response as JSON with this exact format:
{
  "sermon_start": "HH:MM:SS",
  "sermon_end": "HH:MM:SS",
  "confidence": "high|medium|low",
  "reasoning": "Brief explanation of why you identified these boundaries"
}

If you cannot identify a clear sermon, return:
{
  "sermon_start": null,
  "sermon_end": null,
  "confidence": "low",
  "reasoning": "Explanation of why sermon could not be identified"
}"""


def segment_transcript(
    transcript_text: str,
    model: str = "gpt-4o-mini",
    api_key: str | None = None
) -> dict:
    """
    Identify sermon boundaries in a transcript.

    Args:
        transcript_text: Timestamped transcript text
        model: OpenAI model to use
        api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)

    Returns:
        dict with sermon_start, sermon_end, confidence, reasoning
    """
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Here is the church service transcript:\n\n{transcript_text}"}
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )

    result = json.loads(response.choices[0].message.content)
    return result


def extract_sermon_segments(
    segments: list,
    start_time: str,
    end_time: str
) -> list:
    """
    Extract segments that fall within the sermon boundaries.

    Args:
        segments: List of transcript segments with start, end, text
        start_time: Sermon start timestamp (HH:MM:SS)
        end_time: Sermon end timestamp (HH:MM:SS)

    Returns:
        List of segments within the sermon boundaries
    """
    def timestamp_to_seconds(ts: str) -> float:
        parts = ts.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        else:
            return float(parts[0])

    start_sec = timestamp_to_seconds(start_time)
    end_sec = timestamp_to_seconds(end_time)

    sermon_segments = [
        seg for seg in segments
        if seg["start"] >= start_sec and seg["end"] <= end_sec
    ]

    return sermon_segments


def segments_to_text(segments: list) -> str:
    """Convert segments to plain text."""
    return " ".join(seg["text"] for seg in segments)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python segment.py <transcript.json> [model]")
        print("Models: gpt-4o-mini (default), gpt-4o")
        print("\nRequires OPENAI_API_KEY environment variable")
        sys.exit(1)

    transcript_file = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "gpt-4o-mini"

    # Load transcript
    with open(transcript_file) as f:
        data = json.load(f)

    # Format transcript with timestamps for analysis
    from transcribe import segments_to_text as format_segments
    formatted = format_segments(data["segments"], include_timestamps=True)

    print(f"Analyzing transcript with {model}...")
    result = segment_transcript(formatted, model=model)

    print("\n" + "=" * 60)
    print("SEGMENTATION RESULT")
    print("=" * 60)
    print(f"Sermon start: {result.get('sermon_start')}")
    print(f"Sermon end:   {result.get('sermon_end')}")
    print(f"Confidence:   {result.get('confidence')}")
    print(f"Reasoning:    {result.get('reasoning')}")

    # Extract sermon if boundaries found
    if result.get("sermon_start") and result.get("sermon_end"):
        sermon_segments = extract_sermon_segments(
            data["segments"],
            result["sermon_start"],
            result["sermon_end"]
        )
        sermon_text = segments_to_text(sermon_segments)

        print(f"\nExtracted {len(sermon_segments)} segments")
        print(f"Sermon length: ~{len(sermon_text.split())} words")

        # Save extracted sermon
        output = {
            "boundaries": result,
            "segments": sermon_segments,
            "text": sermon_text
        }
        output_file = transcript_file.replace("_transcript.json", "_sermon.json")
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSermon saved to: {output_file}")
