# Dockerfile for hand-gesture-app (Raspberry Pi friendly)
# Build for the Pi's architecture using buildx if needed:
#   docker buildx build --platform linux/arm/v7 -t hand-gesture-app:pi --load .

FROM --platform=$BUILDPLATFORM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Install runtime deps for OpenCV and common media handling. Keep the image
# minimal; add build tools only if pip needs to compile wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        v4l-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only what we need.
COPY requirements.txt pyproject.toml ./
COPY src/ ./src/

# Install Python deps. Note: on Raspberry Pi, the mediapipe wheel might not be
# available via pip for all OS/arch combinations; see README.docker.md for
# troubleshooting and alternative installs.
RUN pip install --no-cache-dir -r requirements.txt

# Expose nothing (uses host networking for camera/server access by default).

ENTRYPOINT ["python", "-m", "src.main"]
