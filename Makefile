# Sermon Scribe Makefile

# Load .env file if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

# Default video URL (override with: make download URL=https://...)
URL ?=
# Whisper model size (tiny, base, small, medium, large)
MODEL ?= medium
# OpenAI model for segmentation
GPT ?= gpt-4o-mini
# Input file for transcription
INPUT ?= output/audio.mp3
# Transcript file for segmentation
TRANSCRIPT ?= audio_transcript.json
# YouTube channel ID for monitoring
CHANNEL_ID ?= $(YOUTUBE_CHANNEL_ID)

# Days to look back for catch-up
DAYS ?= 7

.PHONY: install download transcribe segment cleanup monitor catch-up publish clean help

help:
	@echo "Sermon Scribe Commands:"
	@echo ""
	@echo "  make install              Install Python dependencies"
	@echo "  make monitor              Check for new videos on YouTube channel"
	@echo "  make catch-up             Process recent videos missing transcripts (local)"
	@echo "  make download URL=<url>   Download audio from YouTube video"
	@echo "  make transcribe           Transcribe the downloaded audio"
	@echo "  make segment              Find sermon boundaries in transcript"
	@echo "  make cleanup              Polish the extracted sermon"
	@echo "  make run URL=<url>        Download and transcribe in one step"
	@echo "  make full URL=<url>       Full pipeline: download, transcribe, segment, cleanup"
	@echo "  make publish URL=<url>    Complete pipeline including GitHub Pages publish"
	@echo "  make clean                Remove downloaded files and transcripts"
	@echo ""
	@echo "Options:"
	@echo "  MODEL=medium              Whisper model (tiny/base/small/medium/large)"
	@echo "  GPT=gpt-4o-mini           OpenAI model for segmentation/cleanup"
	@echo "  CHANNEL_ID=UC...          YouTube channel ID for monitoring"
	@echo "  DAYS=7                    Days to look back for catch-up"
	@echo ""
	@echo "Requires: OPENAI_API_KEY environment variable for segmentation/cleanup"
	@echo ""
	@echo "Examples:"
	@echo "  make publish URL=https://www.youtube.com/watch?v=VIDEO_ID"
	@echo "  make full URL=https://www.youtube.com/watch?v=VIDEO_ID"
	@echo "  make catch-up             Process last 7 days and push to GitHub"
	@echo "  make catch-up DAYS=14     Process last 14 days and push to GitHub"

install:
	pip3 install -r requirements.txt

monitor:
ifndef CHANNEL_ID
	$(error CHANNEL_ID is required. Usage: make monitor CHANNEL_ID=UC...)
endif
	python3 src/monitor.py $(CHANNEL_ID)

catch-up:
ifndef CHANNEL_ID
	$(error CHANNEL_ID is required. Usage: make catch-up CHANNEL_ID=UC... or set YOUTUBE_CHANNEL_ID)
endif
	WHISPER_MODEL=$(MODEL) GPT_MODEL=$(GPT) python3 src/process_recent.py --channel $(CHANNEL_ID) --days $(DAYS) --push

download:
ifndef URL
	$(error URL is required. Usage: make download URL=https://youtube.com/watch?v=...)
endif
	@mkdir -p output
	@rm -f output/audio.mp3
	yt-dlp --extractor-args youtube:player_client=android -x --audio-format mp3 -o "output/audio.%(ext)s" "$(URL)"
	@echo "Downloaded to: output/audio.mp3"

transcribe:
	python3 src/transcribe.py $(INPUT) $(MODEL)

segment:
	python3 src/segment.py $(TRANSCRIPT) $(GPT)

cleanup:
	python3 src/cleanup.py audio_sermon.json $(GPT) output/sermon.txt

run:
ifndef URL
	$(error URL is required. Usage: make run URL=https://youtube.com/watch?v=...)
endif
	@mkdir -p output
	@rm -f output/audio.mp3
	yt-dlp --extractor-args youtube:player_client=android -x --audio-format mp3 -o "output/audio.%(ext)s" "$(URL)"
	python3 src/transcribe.py output/audio.mp3 $(MODEL)

full:
ifndef URL
	$(error URL is required. Usage: make full URL=https://youtube.com/watch?v=...)
endif
	@mkdir -p output
	@rm -f output/audio.mp3
	yt-dlp --extractor-args youtube:player_client=android -x --audio-format mp3 -o "output/audio.%(ext)s" "$(URL)"
	python3 src/transcribe.py output/audio.mp3 $(MODEL)
	python3 src/segment.py audio_transcript.json $(GPT)
	python3 src/cleanup.py audio_sermon.json $(GPT) output/sermon.txt
	@echo ""
	@echo "Done! Cleaned sermon saved to: output/sermon.txt"

publish:
ifndef URL
	$(error URL is required. Usage: make publish URL=https://youtube.com/watch?v=...)
endif
	@mkdir -p output
	@rm -f output/audio.mp3
	@echo "Getting video metadata..."
	$(eval VIDEO_ID := $(shell echo "$(URL)" | grep -oP 'v=\K[^&]+'))
	$(eval OEMBED_JSON := $(shell curl -s "https://www.youtube.com/oembed?url=$(URL)&format=json"))
	$(eval TITLE := $(shell echo '$(OEMBED_JSON)' | jq -r '.title'))
	$(eval DATE_STR := $(shell echo "$(TITLE)" | grep -oP '(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}' | head -1))
	$(eval FORMATTED_DATE := $(shell date -j -f "%b. %d, %Y" "$(DATE_STR)" +%Y-%m-%d 2>/dev/null || echo ""))
	$(eval SAFE_TITLE := $(shell echo "$(TITLE)" | tr ' ' '_' | tr -cd '[:alnum:]_-' | cut -c1-100))
	$(eval FILENAME := $(if $(FORMATTED_DATE),sermon_$(FORMATTED_DATE)_$(SAFE_TITLE),sermon_$(SAFE_TITLE)))
	@echo "Title: $(TITLE)"
	@echo "Date: $(FORMATTED_DATE)"
	@echo "Video ID: $(VIDEO_ID)"
	@echo "Filename: $(FILENAME)"
	@echo ""
	@echo "Downloading audio..."
	yt-dlp --extractor-args youtube:player_client=android -x --audio-format mp3 -o "output/audio.%(ext)s" "$(URL)"
	@echo "Transcribing..."
	python3 src/transcribe.py output/audio.mp3 $(MODEL)
	@echo "Segmenting..."
	python3 src/segment.py audio_transcript.json $(GPT)
	@echo "Cleaning up transcript..."
	python3 src/cleanup.py audio_sermon.json $(GPT) "output/$(FILENAME).txt"
	@echo "Publishing to Jekyll..."
	python3 src/publish_sermon.py "output/$(FILENAME).txt" "$(TITLE)" "$(FORMATTED_DATE)" "$(VIDEO_ID)"
	@echo ""
	@echo "Done! Sermon published to docs/_sermons/"
	@echo "Next steps:"
	@echo "  git add output/$(FILENAME).txt docs/_sermons/"
	@echo "  git commit -m 'Add sermon: $(FILENAME)'"
	@echo "  git push"

clean:
	rm -rf output/*
	@echo "Cleaned output directory"
