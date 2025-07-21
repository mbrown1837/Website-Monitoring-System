# Use Python 3.11
FROM python:3.11-slim

# --- NEW SECTION ---
# Install system dependencies for OpenCV and Playwright
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
# --- END NEW SECTION ---

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Expose port
EXPOSE 5001

# Set environment variables
ENV PYTHONPATH=/app/src
ENV FLASK_ENV=production

# Run the application
CMD ["python", "src/app.py"]
