# Sermon Scribe Makefile

# Default video URL (override with: make download URL=https://...)
URL ?=
# Whisper model size (tiny, base, small, medium, large)
MODEL ?= base
# OpenAI model for segmentation
GPT ?= gpt-4o-mini
# Input file for transcription
INPUT ?= output/audio.mp3
# Transcript file for segmentation
TRANSCRIPT ?= audio_transcript.json
# YouTube channel ID for monitoring
CHANNEL_ID ?= $(YOUTUBE_CHANNEL_ID)

.PHONY: install download transcribe segment cleanup monitor clean help

help:
	@echo "Sermon Scribe Commands:"
	@echo ""
	@echo "  make install              Install Python dependencies"
	@echo "  make monitor              Check for new videos on YouTube channel"
	@echo "  make download URL=<url>   Download audio from YouTube video"
	@echo "  make transcribe           Transcribe the downloaded audio"
	@echo "  make segment              Find sermon boundaries in transcript"
	@echo "  make cleanup              Polish the extracted sermon"
	@echo "  make run URL=<url>        Download and transcribe in one step"
	@echo "  make full URL=<url>       Full pipeline: download, transcribe, segment, cleanup"
	@echo "  make clean                Remove downloaded files and transcripts"
	@echo ""
	@echo "Options:"
	@echo "  MODEL=base                Whisper model (tiny/base/small/medium/large)"
	@echo "  GPT=gpt-4o-mini           OpenAI model for segmentation/cleanup"
	@echo "  CHANNEL_ID=UC...          YouTube channel ID for monitoring"
	@echo ""
	@echo "Requires: OPENAI_API_KEY environment variable for segmentation/cleanup"
	@echo ""
	@echo "Example:"
	@echo "  make full URL=https://www.youtube.com/watch?v=VIDEO_ID"

install:
	pip3 install -r requirements.txt

monitor:
ifndef CHANNEL_ID
	$(error CHANNEL_ID is required. Usage: make monitor CHANNEL_ID=UC...)
endif
	python3 src/monitor.py $(CHANNEL_ID)

download:
ifndef URL
	$(error URL is required. Usage: make download URL=https://youtube.com/watch?v=...)
endif
	@mkdir -p output
	@rm -f output/audio.mp3
	yt-dlp -x --audio-format mp3 -o "output/audio.%(ext)s" "$(URL)"
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
	yt-dlp -x --audio-format mp3 -o "output/audio.%(ext)s" "$(URL)"
	python3 src/transcribe.py output/audio.mp3 $(MODEL)

full:
ifndef URL
	$(error URL is required. Usage: make full URL=https://youtube.com/watch?v=...)
endif
	@mkdir -p output
	@rm -f output/audio.mp3
	yt-dlp -x --audio-format mp3 -o "output/audio.%(ext)s" "$(URL)"
	python3 src/transcribe.py output/audio.mp3 $(MODEL)
	python3 src/segment.py audio_transcript.json $(GPT)
	python3 src/cleanup.py audio_sermon.json $(GPT) output/sermon.txt
	@echo ""
	@echo "Done! Cleaned sermon saved to: output/sermon.txt"

clean:
	rm -rf output/*
	@echo "Cleaned output directory"
