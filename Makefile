# Sermon Scribe Makefile

# Default video URL (override with: make download URL=https://...)
URL ?=
# Whisper model size (tiny, base, small, medium, large)
MODEL ?= base
# Input file for transcription
INPUT ?= output/audio.mp3

.PHONY: install download transcribe clean help

help:
	@echo "Sermon Scribe Commands:"
	@echo ""
	@echo "  make install              Install Python dependencies"
	@echo "  make download URL=<url>   Download audio from YouTube video"
	@echo "  make transcribe           Transcribe the downloaded audio"
	@echo "  make transcribe INPUT=<file>  Transcribe a specific file"
	@echo "  make run URL=<url>        Download and transcribe in one step"
	@echo "  make clean                Remove downloaded files and transcripts"
	@echo ""
	@echo "Options:"
	@echo "  MODEL=base                Whisper model (tiny/base/small/medium/large)"
	@echo ""
	@echo "Example:"
	@echo "  make run URL=https://www.youtube.com/watch?v=VIDEO_ID"

install:
	pip3 install -r requirements.txt

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

run:
ifndef URL
	$(error URL is required. Usage: make run URL=https://youtube.com/watch?v=...)
endif
	@mkdir -p output
	@rm -f output/audio.mp3
	yt-dlp -x --audio-format mp3 -o "output/audio.%(ext)s" "$(URL)"
	python3 src/transcribe.py output/audio.mp3 $(MODEL)

clean:
	rm -rf output/*
	@echo "Cleaned output directory"
