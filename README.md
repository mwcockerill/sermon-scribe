# Sermon Scribe

Automated sermon extraction and transcription system for archiving church services.

## Overview

Sermon Scribe monitors a YouTube channel for new uploads, downloads the video, identifies and extracts the sermon portion from the full service, transcribes it, and produces a cleaned-up transcript for archiving on the church website.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  YouTube        │     │   Download   │     │  Transcribe │
│  Monitor        │────▶│   (yt-dlp)   │────▶│  (Whisper)  │
│  (yt-dlp)       │     │              │     │   medium    │
└─────────────────┘     └──────────────┘     └─────────────┘
                                                    │
                                                    ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│ GitHub Pages    │     │   Cleanup    │     │  Segment    │
│ (Jekyll)        │◀────│   (OpenAI)   │◀────│  (OpenAI)   │
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

# Complete pipeline: download, transcribe, segment, cleanup, and publish to GitHub Pages
make publish "URL=https://www.youtube.com/watch?v=VIDEO_ID"

# Full pipeline without publishing (just creates transcript)
make full "URL=https://www.youtube.com/watch?v=VIDEO_ID"

# Process recent videos missing transcripts
make catch-up

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
3. Transcribes with Whisper medium model
4. Segments to find sermon boundaries
5. Cleans up the transcript with GPT-4o-mini
6. Publishes to GitHub Pages (Jekyll) at `docs/_sermons/`
7. Commits and pushes changes
8. Updates `state.json` with the last processed video

**Note:** Skips videos that are scheduled/upcoming until they're available.

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `MODEL` | `medium` | Whisper model: tiny, base, small, medium, large |
| `GPT` | `gpt-4o-mini` | OpenAI model: gpt-4o-mini, gpt-4o |

**Performance Notes:**
- Whisper uses MPS (Metal Performance Shaders) acceleration on Apple Silicon for faster transcription
- Medium model recommended for better accuracy detecting sermons in complex services

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

### 6. Publish
- Create Jekyll markdown file with front matter
- Include metadata: title, date, YouTube video ID
- Generate description from first 150 words
- Save to `docs/_sermons/` for GitHub Pages
- Automatic deployment to church website

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
│       ├── monitor.yml     # Scheduled monitoring (8am/8pm UTC)
│       └── catch-up.yml    # Manual batch processing
├── src/
│   ├── __init__.py
│   ├── transcribe.py       # Whisper transcription
│   ├── segment.py          # Sermon boundary detection
│   ├── cleanup.py          # Transcript polishing
│   ├── monitor.py          # YouTube channel monitoring
│   ├── publish_sermon.py   # Jekyll/GitHub Pages publishing
│   └── process_recent.py   # Batch process recent videos
├── docs/
│   └── _sermons/           # Jekyll sermon posts (GitHub Pages)
└── output/
    └── sermon_*.txt        # Generated transcripts
```

## Roadmap

- [x] Set up project structure and dependencies
- [x] Implement transcription module (Whisper)
- [x] Implement segmentation module (OpenAI)
- [x] Implement cleanup module (OpenAI)
- [x] Implement YouTube monitoring
- [x] GitHub Actions automation
- [x] GitHub Pages publishing (Jekyll)
- [x] Batch processing for catch-up
- [x] Handle upcoming/scheduled videos
- [x] MPS acceleration for Apple Silicon
- [ ] Add configuration management (YAML)
- [ ] Support for multiple channels
- [ ] Search functionality for sermons

## License

Private - for church use only
