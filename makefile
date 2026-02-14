# MuseAid Makefile
# Project: MuseAid

# Variables
PROJECT_NAME = MuseAid
BUILD_DIR = build
SRC_DIR = src
DIST_DIR = dist

# Phony targets
.PHONY: help all build clean install test run dev lint format setup

## all: Build the entire project
all: clean build

setup:
	sudo apt update
	sudo apt install gpg curl
	sudo apt update
	sudo apt install -y build-essential git lsb-release libcurl4-openssl-dev libssl-dev pkg-config libv4l-dev libgles2-mesa-dev libunwind-dev gpg curl
	sudo apt update
	sudo apt install libsmartspectra-dev

build:
	@echo "Building $(PROJECT_NAME)..."
	# Add build commands here

clean:
