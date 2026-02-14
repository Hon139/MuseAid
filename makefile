# MuseAid Makefile
# Project: MuseAid

# Variables
PROJECT_NAME = MuseAid
BUILD_DIR = build
SRC_DIR = src
DIST_DIR = dist

# Phony targets
.PHONY: help all build clean install test run dev lint format setup \
        sync server composition-app gesture-app run-all stop

## all: Build the entire project
all: clean build

# ---------- Run targets ----------

UV_SYNC = uv sync --python-preference only-system

## sync: Install dependencies for all sub-projects
sync:
	cd server          && $(UV_SYNC)
	cd Composition_App && $(UV_SYNC)
	cd hand-gesture-app && $(UV_SYNC)

## server: Start the MuseAid server (port 8000)
server:
	cd server && $(UV_SYNC) && uv run uvicorn museaid_server.main:app --reload --host 0.0.0.0 --port 8000

## composition-app: Start the Composition App
composition-app:
	cd Composition_App && $(UV_SYNC) && uv run music-app

## gesture-app: Start the hand-gesture app
gesture-app:
	cd hand-gesture-app && $(UV_SYNC) && uv run python -m src.main

## run-all: Launch server, composition app, and gesture app concurrently (Linux/macOS)
run-all: sync
	@echo "Starting all MuseAid components..."
	cd server          && uv run uvicorn museaid_server.main:app --reload --host 0.0.0.0 --port 8000 &
	@sleep 3
	cd Composition_App && uv run music-app &
	cd hand-gesture-app && uv run python -m src.main &
	@echo "All components started. Press Ctrl+C to stop."
	@wait

## stop: Kill all MuseAid-related processes
stop:
	-pkill -f "uvicorn museaid_server" 2>/dev/null || true
	-pkill -f "music.app" 2>/dev/null || true
	-pkill -f "src.main" 2>/dev/null || true
	@echo "Stopped all MuseAid processes."

# ---------- Setup ----------

setup:
	curl -s "https://presage-security.github.io/PPA/KEY.gpg" | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/presage-technologies.gpg >/dev/null
	sudo curl -s --compressed -o /etc/apt/sources.list.d/presage-technologies.list "https://presage-security.github.io/PPA/presage-technologies.list"
	sudo apt update
	sudo apt install gpg curl
	sudo apt update
	sudo apt install -y build-essential git lsb-release libcurl4-openssl-dev libssl-dev pkg-config libv4l-dev libgles2-mesa-dev libunwind-dev gpg curl
	sudo apt update
	sudo apt install libsmartspectra-dev
	npm install @elevenlabs/elevenlabs-js

# ---------- Build / Clean ----------

## build: Create / refresh virtual environments for all sub-projects
build:
	@echo "Building $(PROJECT_NAME) — syncing virtual environments..."
	cd server          && $(UV_SYNC)
	cd Composition_App && $(UV_SYNC)
	cd hand-gesture-app && $(UV_SYNC)
	@echo "Build complete."

## clean: Remove all .venv directories and Python caches
clean:
	@echo "Cleaning $(PROJECT_NAME)..."
	rm -rf server/.venv Composition_App/.venv hand-gesture-app/.venv
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete."
