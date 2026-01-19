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
│  (JSON/MD)      │◀────│   (Claude)   │◀────│  (Claude)   │
│                 │     │              │     │             │
└─────────────────┘     └──────────────┘     └─────────────┘
```

## Pipeline Stages

### 1. Monitor
- Poll YouTube channel for new video uploads
- Options: YouTube Data API v3 or RSS feed
- Trigger download when new video detected

### 2. Download
- Download audio from YouTube video using `yt-dlp`
- Extract audio only (no video needed for transcription)
- Store temporarily for processing

### 3. Transcribe
- Transcribe audio using OpenAI Whisper
- Output includes timestamps for segmentation
- Full service transcript with timing data

### 4. Segment
- Send transcript to Claude API
- Identify sermon start/end based on content analysis
- Look for: extended teaching, scripture references, single speaker
- Exclude: announcements, worship music, prayers, offering

### 5. Cleanup
- Polish the extracted sermon transcript
- Fix punctuation and paragraph breaks
- Remove filler words and false starts
- Format for readability

### 6. Output
- Generate final transcript (Markdown or JSON)
- Ready for upload to church website

## Tech Stack

- **Language:** Python
- **Video Download:** yt-dlp
- **Transcription:** OpenAI Whisper
- **AI Processing:** Claude API (Anthropic)
- **YouTube Monitoring:** YouTube Data API v3 / RSS

## Dependencies

```
yt-dlp
openai-whisper
anthropic
google-api-python-client
```

## Project Structure

```
sermon-scribe/
├── README.md
├── requirements.txt
├── src/
│   ├── monitor.py      # YouTube channel monitoring
│   ├── download.py     # Video/audio download
│   ├── transcribe.py   # Whisper transcription
│   ├── segment.py      # Sermon boundary detection
│   ├── cleanup.py      # Transcript polishing
│   └── main.py         # Pipeline orchestration
├── output/             # Generated transcripts
└── config/
    └── config.yaml     # API keys, channel ID, settings
```

## Roadmap

- [ ] Set up project structure and dependencies
- [ ] Implement transcription module (Whisper)
- [ ] Implement segmentation module (Claude)
- [ ] Implement cleanup module (Claude)
- [ ] Implement download module (yt-dlp)
- [ ] Implement YouTube monitoring
- [ ] Add configuration management
- [ ] End-to-end pipeline integration
- [ ] Testing with real service videos

## Usage

*(Coming soon)*

## License

Private - for church use only
