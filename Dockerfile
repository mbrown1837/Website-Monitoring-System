# Use Python 3.11
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install Playwright browsers
RUN playwright install chromium

# Expose port
EXPOSE 5001

# Set environment variables
ENV PYTHONPATH=/app/src
ENV FLASK_ENV=production

# Run the application
CMD ["python", "src/app.py"]
