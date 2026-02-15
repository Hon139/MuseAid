# MuseAid Makefile
# Project: MuseAid

# Variables
PROJECT_NAME = MuseAid
BUILD_DIR = build
SRC_DIR = src
DIST_DIR = dist

# Phony targets
.PHONY: help all build clean install test run dev lint format setup \
	sync server composition-app gesture-app run-all stop install-python build-gem run-gem

## all: Build the entire project
all: clean build

# ---------- Run targets ----------

## uv sync: try system first, then fall back to managed (grouped so && runs after)
UV_SYNC = (uv sync --python-preference system || uv sync --python-preference managed)

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

## run-all: Launch server, composition app, and gesture app concurrently
run-all: sync
ifeq ($(OS),Windows_NT)
	@echo "Starting all MuseAid components in separate terminals (Windows)..."
	start "MuseAid Server" cmd /k "cd /d server && uv run uvicorn museaid_server.main:app --reload --host 0.0.0.0 --port 8000"
	powershell -NoProfile -Command "Start-Sleep -Seconds 3"
	start "Composition App" cmd /k "cd /d Composition_App && uv run music-app"
	start "Gesture App" cmd /k "cd /d hand-gesture-app && uv run python -m src.main"
	@echo "All components started in separate windows. Use 'make stop' to stop background processes."
else
	@echo "Starting all MuseAid components..."
	cd server          && uv run uvicorn museaid_server.main:app --reload --host 0.0.0.0 --port 8000 &
	@sleep 3
	cd Composition_App && uv run music-app &
	cd hand-gesture-app && uv run python -m src.main &
	@echo "All components started. Press Ctrl+C to stop."
	@wait
endif

## stop: Kill all MuseAid-related processes
stop:
ifeq ($(OS),Windows_NT)
	-powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'museaid_server.main:app|music-app|python -m src.main' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
	@echo "Stopped all MuseAid processes."
else
	-pkill -f "uvicorn museaid_server" 2>/dev/null || true
	-pkill -f "music.app" 2>/dev/null || true
	-pkill -f "src.main" 2>/dev/null || true
	@echo "Stopped all MuseAid processes."
endif

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

## install-python: optional helper to install Python 3.13 on Debian/Ubuntu (requires sudo)
install-python:
	@echo "Checking for python3.13..."
	@if command -v python3.13 >/dev/null 2>&1; then \
		echo "python3.13 already installed: $$(python3.13 --version)"; \
	else \
		if [ -f /etc/os-release ]; then . /etc/os-release; fi; \
		if echo "$${ID_LIKE:-} $${ID:-}" | grep -Eiq "debian|ubuntu"; then \
			echo "Detected Debian/Ubuntu family — installing python3.13 via apt (requires sudo)"; \
			sudo apt-get update && sudo apt-get install -y python3.13 python3.13-venv python3.13-dev || \
			(echo "apt install failed. You may need to enable a PPA or install manually." && exit 1); \
		else \
			echo "Automatic installer only supports Debian/Ubuntu. Please install Python 3.13 manually for your distro."; \
			exit 1; \
		fi; \
	fi

## clean: Remove all .venv directories and Python caches
clean:
	@echo "Cleaning $(PROJECT_NAME)..."
	rm -rf server/.venv Composition_App/.venv hand-gesture-app/.venv
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete."

## build-gem: Create/refresh virtual environment for the ElevenL n gem component
build-gem:
	@echo "Building ElevenL n gem venv..."
	@if [ ! -d "ElevenL n gem/venv" ]; then \
		echo "Creating venv in 'ElevenL n gem'..."; \
		cd "ElevenL n gem" && python3 -m venv venv; \
	fi
	@echo "Installing google-genai into ElevenL n gem venv..."
	@cd "ElevenL n gem" && ./venv/bin/pip install --upgrade pip
	@cd "ElevenL n gem" && ./venv/bin/pip install -q -U google-genai
	@echo "✅ ElevenL n gem venv ready."

## run-gem: Run `py/gem.py` in the ElevenL n gem component (requires GEMINI_API_KEY set)
run-gem: build-gem
	@echo "Running gem.py (ElevenL n gem)..."
	@cd "ElevenL n gem" && GEMINI_API_KEY=$$GEMINI_API_KEY ./venv/bin/python py/gem.py
