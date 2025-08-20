# Base image: lightweight Python
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed for some libs like lxml, requests, sqlite3)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirement files first (better caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Ensure data folder exists (for sqlite)
RUN mkdir -p data

# Expose port (if later we add FastAPI dashboard)

# Run the crawler
CMD ["python", "main.py"]