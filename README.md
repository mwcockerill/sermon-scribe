# Sermon Scribe

Automated sermon extraction and transcription system for archiving church services.

## Overview

Sermon Scribe monitors a YouTube channel for new uploads, downloads the video, identifies and extracts the sermon portion from the full service, transcribes it, and produces a cleaned-up transcript for archiving on the church website.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  YouTube        │     │   Download   │     │  Transcribe │
│  Monitor        │────▶│   (yt-dlp)   │────▶│  (Whisper)  │
│  (yt-dlp)       │     │              │     │             │
└─────────────────┘     └──────────────┘     └─────────────┘
                                                    │
                                                    ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  Output         │     │   Cleanup    │     │  Segment    │
│  (.txt)         │◀────│   (OpenAI)   │◀────│  (OpenAI)   │
│                 │     │              │     │             │
└─────────────────┘     └──────────────┘     └─────────────┘
```

## Setup

### Local Development

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

### GitHub Actions (Automated Monitoring)

To enable automatic monitoring and processing:

1. **Add GitHub Secrets** (Settings → Secrets and variables → Actions):
   - `OPENAI_API_KEY` - Your OpenAI API key
   - `YOUTUBE_CHANNEL_ID` - The channel ID to monitor

2. **Find Your Channel ID**:
   - Go to the YouTube channel
   - View page source and search for `channelId`
   - Or use a service like [Comment Picker](https://commentpicker.com/youtube-channel-id.php)

3. **Enable the Workflow**:
   - The workflow runs at 8am and 8pm UTC automatically
   - You can also trigger it manually from Actions tab
   - Use "Force URL" input to process a specific video

4. **First Run**:
   - The first run initializes the state with the latest video
   - Subsequent runs will process any new uploads

## Usage

### Manual (Local)

```bash
# See all commands
make help

# Full pipeline: download, transcribe, segment, cleanup
make full "URL=https://www.youtube.com/watch?v=VIDEO_ID"

# Or run steps individually:
make download "URL=https://www.youtube.com/watch?v=VIDEO_ID"
make transcribe
make segment
make cleanup

# Check for new videos (without processing)
python src/monitor.py YOUR_CHANNEL_ID
```

### Automated (GitHub Actions)

The workflow automatically:
1. Checks for new videos at 8am and 8pm UTC
2. Downloads and processes new uploads
3. Commits the cleaned transcript to `output/sermon_DATE_TITLE.txt`
4. Updates `state.json` with the last processed video

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `MODEL` | `base` | Whisper model: tiny, base, small, medium, large |
| `GPT` | `gpt-4o-mini` | OpenAI model: gpt-4o-mini, gpt-4o |

## Pipeline Stages

### 1. Monitor
- Check YouTube channel for new uploads using yt-dlp
- Compare against last processed video ID
- Trigger pipeline when new video detected

### 2. Download
- Download audio from YouTube video using `yt-dlp`
- Extract audio only (MP3) to save space
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

### 5. Cleanup
- Polish the extracted sermon transcript
- Fix transcription errors (e.g., "Maygai" → "Magi")
- Add proper punctuation and paragraph breaks
- Remove filler words and false starts

### 6. Output
- Generate final transcript as plain text
- Ready for upload to church website

## Tech Stack

- **Language:** Python
- **Video Download:** yt-dlp
- **Transcription:** OpenAI Whisper (local)
- **AI Processing:** OpenAI API (GPT-4o-mini)
- **Monitoring:** yt-dlp (channel video listing)
- **Automation:** GitHub Actions

## Project Structure

```
sermon-scribe/
├── README.md
├── Makefile
├── requirements.txt
├── state.json              # Tracks last processed video
├── .env.example
├── .env                    # Local config (gitignored)
├── .github/
│   └── workflows/
│       └── monitor.yml     # GitHub Actions workflow
├── src/
│   ├── __init__.py
│   ├── transcribe.py       # Whisper transcription
│   ├── segment.py          # Sermon boundary detection
│   ├── cleanup.py          # Transcript polishing
│   └── monitor.py          # YouTube channel monitoring
└── output/
    └── sermon_*.txt        # Generated transcripts
```

## Roadmap

- [x] Set up project structure and dependencies
- [x] Implement transcription module (Whisper)
- [x] Implement segmentation module (OpenAI)
- [x] Implement cleanup module (OpenAI)
- [x] Implement YouTube monitoring (RSS)
- [x] GitHub Actions automation
- [ ] Add configuration management (YAML)
- [ ] Support for multiple channels
- [ ] Web interface for browsing transcripts

## License

Private - for church use only
