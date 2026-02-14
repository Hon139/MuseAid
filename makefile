# MuseAid Makefile
# Project: MuseAid

# Variables
PROJECT_NAME = MuseAid
BUILD_DIR = build
SRC_DIR = src
DIST_DIR = dist
VENV_DIR = venv

# Default target
.DEFAULT_GOAL := help

# Phony targets
.PHONY: help all build clean install test run dev lint format setup venv run-gesture demo-gesture

## all: Build the entire project
all: venv build

## venv: Create and set up virtual environment
venv:
	@echo "Setting up virtual environment..."
	@if [ ! -d "$(VENV_DIR)" ]; then \
		python3 -m venv $(VENV_DIR); \
	fi
	@echo "Installing dependencies..."
	@$(VENV_DIR)/bin/pip install --upgrade pip
	@$(VENV_DIR)/bin/pip install elevenlabs python-dotenv
	@echo "Virtual environment ready. Activate with: source $(VENV_DIR)/bin/activate"

## build: Build all project components (Composition App, hand-gesture-app, Presage)
build:
	@echo "Building $(PROJECT_NAME) components..."
	@# Build Composition App (uv-based)
	@if [ -d "Composition_App" ]; then \
		echo "Building Composition App..."; \
		cd Composition_App && \
		if command -v uv >/dev/null 2>&1; then \
			uv build; \
		else \
			echo "uv not found, installing dependencies with venv pip..."; \
			../$(VENV_DIR)/bin/pip install -e .; \
		fi \
	fi
	@# Build hand-gesture-app (uv-based)
	@if [ -d "hand-gesture-app" ]; then \
		echo "Building hand-gesture-app..."; \
		cd hand-gesture-app && \
		if command -v uv >/dev/null 2>&1; then \
			uv build; \
		else \
			echo "uv not found, installing dependencies with venv pip..."; \
			../$(VENV_DIR)/bin/pip install -e .; \
		fi \
	fi
	@# Build Presage (C/C++ if makefile exists)
	@if [ -d "Presage" ] && [ -f "Presage/Makefile" ]; then \
		echo "Building Presage..."; \
		cd Presage && make; \
	fi
	@echo "Build complete!"
	curl -LsSf https://astral.sh/uv/install.sh | sh

## setup: Set up the development environment
setup: venv
	@echo "Setting up development environment..."
	@# Install uv if not present
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "Installing uv..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi

## clean: Remove build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(BUILD_DIR) $(DIST_DIR)
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@# Clean Python package builds
	@find . -name "dist" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
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
run-tts: venv
	@echo "Running TTS example..."
	@source $(VENV_DIR)/bin/activate && python ElevenL/py/TTS.py

## run-stt: Run ElevenLabs STT example  
run-stt: venv
	@echo "Running STT example..."
	@source $(VENV_DIR)/bin/activate && python ElevenL/py/STT.py

## run-gesture: Run hand gesture recognition app
run-gesture: venv build
	cd hand-gesture-app 
	uv sync 
	uv run python -m src.main 
# 	@echo "Starting hand gesture recognition..."
# 	@echo "Press 'q' to quit, 'ESC' to exit"
# 	@cd hand-gesture-app && ../$(VENV_DIR)/bin/python -m src.main

## demo-gesture: Run gesture recognition demo without camera
demo-gesture: venv 
	@echo "Running gesture recognition demo..."
	@cd hand-gesture-app && ../$(VENV_DIR)/bin/python demo.py
