# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies (FFMPEG is critical for yt-dlp)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run the bot (This is the default command, but render.yaml overrides it anyway)
CMD ["python", "bot.py"]