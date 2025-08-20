# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for compiling some Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libxml2-dev \
    libxslt1-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
# Torch CPU-only version to avoid GPU build issues
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source code
COPY . .

# Make data and logs folders (for persistent volumes)
RUN mkdir -p data logs

# Expose port if using FastAPI later

# Run main.py
CMD ["python", "main.py"]