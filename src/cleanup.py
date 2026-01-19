"""
Cleanup module using OpenAI.

Polishes raw sermon transcripts by fixing transcription errors,
adding proper punctuation, paragraph breaks, and removing filler words.
"""

import os
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")


SYSTEM_PROMPT = """You are an expert editor specializing in religious sermon transcripts. Your task is to clean up a raw speech-to-text transcript and produce a polished, readable version.

Instructions:
1. Fix transcription errors (e.g., "Maygai" should be "Magi", phonetic misspellings)
2. Add proper punctuation and capitalization
3. Break into logical paragraphs (every 3-5 sentences or at natural topic shifts)
4. Remove filler words ("um", "uh", "you know", false starts)
5. Fix grammar issues caused by speech-to-text errors
6. Preserve the speaker's voice and style - don't rewrite, just clean up
7. Keep all scripture references and theological terms accurate
8. Do NOT add content that wasn't in the original
9. Do NOT remove meaningful content

Output the cleaned transcript as plain text with proper paragraphs. Do not include any commentary or notes - just the cleaned sermon text."""


def cleanup_sermon(
    sermon_text: str,
    model: str = "gpt-4o-mini",
    api_key: str | None = None
) -> str:
    """
    Clean up a raw sermon transcript.

    Args:
        sermon_text: Raw transcript text
        model: OpenAI model to use
        api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)

    Returns:
        Cleaned transcript as a string
    """
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Please clean up this sermon transcript:\n\n{sermon_text}"}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content


def save_cleaned_sermon(
    cleaned_text: str,
    output_path: str,
    title: str | None = None
) -> None:
    """
    Save cleaned sermon to a text file.

    Args:
        cleaned_text: The cleaned sermon text
        output_path: Path to save the file
        title: Optional title to add at the top
    """
    with open(output_path, "w") as f:
        if title:
            f.write(f"{title}\n\n")
        f.write(cleaned_text)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python cleanup.py <sermon.json> [model] [output.txt]")
        print("Models: gpt-4o-mini (default), gpt-4o")
        print("\nRequires OPENAI_API_KEY environment variable")
        sys.exit(1)

    sermon_file = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "gpt-4o-mini"

    # Determine output path
    if len(sys.argv) > 3:
        output_file = sys.argv[3]
    else:
        output_file = sermon_file.replace("_sermon.json", "_cleaned.txt").replace(".json", "_cleaned.txt")

    # Load sermon
    with open(sermon_file) as f:
        data = json.load(f)

    # Get the text - handle both formats
    if isinstance(data, dict) and "text" in data:
        sermon_text = data["text"]
    elif isinstance(data, str):
        sermon_text = data
    else:
        sermon_text = str(data)

    print(f"Cleaning sermon with {model}...")
    print(f"Input length: {len(sermon_text.split())} words")

    cleaned = cleanup_sermon(sermon_text, model=model)

    print(f"Output length: {len(cleaned.split())} words")

    # Save to file
    save_cleaned_sermon(cleaned, output_file)
    print(f"\nCleaned sermon saved to: {output_file}")

    # Also print preview
    print("\n" + "=" * 60)
    print("PREVIEW (first 500 chars)")
    print("=" * 60)
    print(cleaned[:500] + "...")
