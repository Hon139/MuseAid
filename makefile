# MuseAid Makefile
# Project: MuseAid

# Variables
PROJECT_NAME = MuseAid
BUILD_DIR = build
SRC_DIR = src
DIST_DIR = dist

# Phony targets
<<<<<<< HEAD
.PHONY: help all build build-gesture build-composition build-elevenlabs clean install test run dev lint format setup venv run-gesture demo-gesture
=======
.PHONY: help all build clean install test run dev lint format setup \
        sync server composition-app gesture-app run-all stop
>>>>>>> 69799dd (added http server and extras)

## all: Build the entire project
all: clean build

# ---------- Run targets ----------

<<<<<<< HEAD
## build: Build all project components
build: build-elevenlabs build-composition build-gesture
	@echo "All components built successfully!"

## build-elevenlabs: Build ElevenL components with dedicated venv
build-elevenlabs:
	@echo "Building ElevenL components..."
	@if [ ! -d "ElevenL/venv" ]; then \
		echo "Creating ElevenL virtual environment..."; \
		python3 -m venv ElevenL/venv; \
	fi
	@echo "Installing ElevenL dependencies..."
	@ElevenL/venv/bin/pip install --upgrade pip
	@ElevenL/venv/bin/pip install elevenlabs python-dotenv
	@echo "✅ ElevenL build complete!"

## build-composition: Build Composition App with dedicated venv
build-composition:
	@echo "Building Composition App..."
	@if [ -d "Composition_App" ]; then \
		if [ ! -d "Composition_App/venv" ]; then \
			echo "Creating Composition App virtual environment..."; \
			python3 -m venv Composition_App/venv; \
		fi; \
		echo "Installing Composition App dependencies..."; \
		Composition_App/venv/bin/pip install --upgrade pip; \
		if command -v uv >/dev/null 2>&1; then \
			cd Composition_App && uv sync; \
		else \
			Composition_App/venv/bin/pip install -e Composition_App/; \
		fi; \
		echo "✅ Composition App build complete!"; \
	else \
		echo "⚠️  Composition_App directory not found"; \
	fi

## build-gesture: Build hand-gesture-app with dedicated venv  
build-gesture:
	@echo "Building hand-gesture-app..."
	@if [ -d "hand-gesture-app" ]; then \
		if [ ! -d "hand-gesture-app/venv" ]; then \
			echo "Creating hand-gesture-app virtual environment..."; \
			python3 -m venv hand-gesture-app/venv; \
		fi; \
		echo "Installing hand-gesture-app dependencies..."; \
		hand-gesture-app/venv/bin/pip install --upgrade pip; \
		if command -v uv >/dev/null 2>&1; then \
			cd hand-gesture-app && uv sync; \
		else \
			hand-gesture-app/venv/bin/pip install -e hand-gesture-app/; \
		fi; \
		echo "✅ Hand-gesture-app build complete!"; \
	else \
		echo "⚠️  hand-gesture-app directory not found"; \
	fi

## setup: Set up the development environment
setup: venv
	@echo "Setting up development environment..."
	@# Install uv if not present
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "Installing uv..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi

## clean: Remove build artifacts and virtual environments
=======
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
>>>>>>> 69799dd (added http server and extras)
clean:
	@echo "Cleaning $(PROJECT_NAME)..."
	rm -rf server/.venv Composition_App/.venv hand-gesture-app/.venv
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
<<<<<<< HEAD
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@# Clean Python package builds
	@find . -name "dist" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
	@# Clean component virtual environments
	@echo "Removing component virtual environments..."
	rm -rf ElevenL/venv Composition_App/venv hand-gesture-app/venv
	@# Clean Presage if makefile exists
	@if [ -d "Presage" ] && [ -f "Presage/Makefile" ]; then \
		cd Presage && make clean; \
	fi

## install: Install dependencies for all components
install: venv
	@echo "Installing all dependencies..."
	@# Install ElevenL dependencies
	@$(VENV_DIR)/bin/pip install elevenlabs python-dotenv
	@# Install Composition App dependencies
	@if [ -d "Composition_App" ]; then \
		cd Composition_App && \
		if command -v uv >/dev/null 2>&1; then \
			uv sync; \
		else \
			../$(VENV_DIR)/bin/pip install -e .; \
		fi \
	fi
	@# Install hand-gesture-app dependencies  
	@if [ -d "hand-gesture-app" ]; then \
		cd hand-gesture-app && \
		if command -v uv >/dev/null 2>&1; then \
			uv sync; \
		else \
			../$(VENV_DIR)/bin/pip install -e .; \
		fi \
	fi

## run-tts: Run ElevenLabs TTS example
run-tts: build-elevenlabs
	@echo "Running TTS example..."
	@ElevenL/venv/bin/python ElevenL/py/TTS.py

## run-stt: Run ElevenLabs STT example  
run-stt: build-elevenlabs
	@echo "Running STT example..."
	@ElevenL/venv/bin/python ElevenL/py/STT.py

## run-gesture: Run hand gesture recognition app
run-gesture: build-gesture
	@echo "Starting hand gesture recognition..."
	@echo "Press 'q' to quit, 'ESC' to exit"
	@if command -v uv >/dev/null 2>&1 && [ -f "hand-gesture-app/pyproject.toml" ]; then \
		cd hand-gesture-app && uv run python -m src.main; \
	else \
		hand-gesture-app/venv/bin/python -m hand-gesture-app.src.main; \
	fi

## demo-gesture: Run gesture recognition demo without camera
demo-gesture: build-gesture
	@echo "Running gesture recognition demo..."
	@hand-gesture-app/venv/bin/python hand-gesture-app/demo.py

=======
	@echo "Clean complete."
>>>>>>> 69799dd (added http server and extras)
