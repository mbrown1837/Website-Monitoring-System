#!/bin/bash

# Production start script for Website Monitoring System

echo "🚀 Starting Website Monitoring System in production mode..."

# Set environment variables
export FLASK_ENV=production
export PYTHONPATH=/app

# Create necessary directories
mkdir -p /app/data/snapshots
mkdir -p /app/data/crawl_results
mkdir -p /app/data/performance
mkdir -p /app/data/visual_diffs
mkdir -p /app/data/blur_detection
mkdir -p /app/logs

# Set permissions
chmod -R 755 /app/data
chmod -R 755 /app/logs

# Run database migration if needed
echo "🗄️ Running database migration..."
python scripts/simple_migration.py

# Start the application with Gunicorn
echo "🌐 Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:5001 \
    --workers 2 \
    --worker-class gevent \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --timeout 120 \
    --keep-alive 5 \
    --preload \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    main:app
