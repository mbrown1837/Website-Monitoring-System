#!/bin/bash

# Production startup script for Website Monitoring System

set -e

echo "🚀 Starting Website Monitoring System..."

# Create necessary directories
mkdir -p /app/data
mkdir -p /app/logs
mkdir -p /app/screenshots
mkdir -p /app/config

# Set proper permissions
chmod 755 /app/data
chmod 755 /app/logs
chmod 755 /app/screenshots
chmod 755 /app/config

# Check if database exists, if not initialize
if [ ! -f "/app/data/website_monitor.db" ]; then
    echo "📊 Initializing database..."
    python -c "
import sys
sys.path.append('/app')
from src.website_manager_sqlite import WebsiteManager
from src.history_manager import HistoryManager
from src.scheduler_db import get_scheduler_db_manager

# Initialize database
wm = WebsiteManager()
hm = HistoryManager()
sdb = get_scheduler_db_manager()
print('Database initialized successfully')
"
fi

# Start the application
echo "🌐 Starting Flask application..."
exec python src/app.py
