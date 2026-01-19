# Sermon Scribe

Automated sermon extraction and transcription system for archiving church services.

## Overview

Sermon Scribe monitors a YouTube channel for new uploads, downloads the video, identifies and extracts the sermon portion from the full service, transcribes it, and produces a cleaned-up transcript for archiving on the church website.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  YouTube        │     │   Download   │     │  Transcribe │
│  Monitor        │────▶│   (yt-dlp)   │────▶│  (Whisper)  │
│  (YT Data API)  │     │              │     │             │
└─────────────────┘     └──────────────┘     └─────────────┘
                                                    │
                                                    ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  Output         │     │   Cleanup    │     │  Segment    │
│  (JSON/MD)      │◀────│   (OpenAI)   │◀────│  (OpenAI)   │
│                 │     │              │     │             │
└─────────────────┘     └──────────────┘     └─────────────┘
```

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   make install
   ```
3. Create your environment file:
   ```bash
   cp .env.example .env
   ```
4. Add your OpenAI API key to `.env`:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```

## Usage

```bash
# See all commands
make help

# Download, transcribe, and segment in one step
make full URL=https://www.youtube.com/watch?v=VIDEO_ID

# Or run steps individually:
make download URL=https://www.youtube.com/watch?v=VIDEO_ID
make transcribe
make segment

# Use different models
make full URL=... MODEL=large GPT=gpt-4o
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `MODEL` | `base` | Whisper model: tiny, base, small, medium, large |
| `GPT` | `gpt-4o-mini` | OpenAI model: gpt-4o-mini, gpt-4o |

## Pipeline Stages

### 1. Monitor (coming soon)
- Poll YouTube channel for new video uploads
- Options: YouTube Data API v3 or RSS feed
- Trigger download when new video detected

### 2. Download
- Download audio from YouTube video using `yt-dlp`
- Extract audio only (no video needed for transcription)
- Store temporarily for processing

### 3. Transcribe
- Transcribe audio using OpenAI Whisper (runs locally)
- Output includes timestamps for segmentation
- Full service transcript with timing data

### 4. Segment
- Send transcript to OpenAI API
- Identify sermon start/end based on content analysis
- Look for: extended teaching, scripture references, single speaker
- Exclude: announcements, worship music, prayers, offering

### 5. Cleanup (coming soon)
- Polish the extracted sermon transcript
- Fix punctuation and paragraph breaks
- Remove filler words and false starts
- Format for readability

### 6. Output
- Generate final transcript (JSON)
- Ready for upload to church website

## Tech Stack

- **Language:** Python
- **Video Download:** yt-dlp
- **Transcription:** OpenAI Whisper (local)
- **AI Processing:** OpenAI API (GPT-4o-mini)
- **YouTube Monitoring:** YouTube Data API v3 / RSS (coming soon)

## Project Structure

```
sermon-scribe/
├── README.md
├── Makefile
├── requirements.txt
├── .env.example
├── .env              # Your local config (gitignored)
├── src/
│   ├── __init__.py
│   ├── transcribe.py   # Whisper transcription
│   └── segment.py      # Sermon boundary detection (OpenAI)
├── output/             # Generated transcripts (gitignored)
└── config/
```

## Roadmap

- [x] Set up project structure and dependencies
- [x] Implement transcription module (Whisper)
- [x] Implement segmentation module (OpenAI)
- [ ] Implement cleanup module (OpenAI)
- [ ] Implement download module (Python wrapper)
- [ ] Implement YouTube monitoring
- [ ] Add configuration management
- [ ] End-to-end pipeline integration
- [ ] Testing with real service videos

## License

Private - for church use only
