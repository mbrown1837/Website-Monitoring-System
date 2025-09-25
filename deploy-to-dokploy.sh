#!/bin/bash

# Dokploy Deployment Script for Website Monitoring System
# Run this script to prepare your project for Dokploy deployment

echo "🚀 Preparing Website Monitoring System for Dokploy deployment..."

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p data/snapshots
mkdir -p data/crawl_results
mkdir -p data/performance
mkdir -p data/visual_diffs
mkdir -p data/blur_detection
mkdir -p logs

# Set permissions
echo "🔐 Setting permissions..."
chmod +x start.sh
chmod +x deploy-to-dokploy.sh

# Create .env.example file
echo "📝 Creating .env.example file..."
cat > .env.example << EOF
# Dokploy Environment Variables
# Copy this to .env and fill in your values

# Application
DASHBOARD_URL=http://your-domain.com
SECRET_KEY=your-secret-key-here
LOG_LEVEL=INFO
TZ=UTC
SCHEDULER_ENABLED=true

# Database
DATABASE_URL=sqlite:///data/website_monitor.db

# WebSocket
WEBSOCKET_HOST=0.0.0.0
WEBSOCKET_PORT=8765

# SMTP Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
EOF

# Create production requirements
echo "📦 Creating production requirements..."
cp requirements.txt requirements.production.txt

# Add production-specific packages
echo "gunicorn==21.2.0" >> requirements.production.txt
echo "gevent==23.9.1" >> requirements.production.txt

# Create production start script
echo "🔄 Creating production start script..."
cat > start.production.sh << 'EOF'
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
EOF

chmod +x start.production.sh

# Create .dockerignore
echo "🐳 Creating .dockerignore..."
cat > .dockerignore << EOF
# Git
.git
.gitignore

# Documentation
docs/
*.md
!README.md

# Development files
.env
.env.local
.env.development
.env.test

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/

# Testing
tests/
.pytest_cache/
.coverage

# Logs
*.log
logs/

# Data (will be mounted as volumes)
data/snapshots/
data/crawl_results/
data/performance/
data/visual_diffs/
data/blur_detection/

# Temporary files
*.tmp
*.temp
EOF

echo "✅ Preparation complete!"
echo ""
echo "📋 Next steps:"
echo "1. Copy .env.example to .env and fill in your values"
echo "2. Push your code to Git repository"
echo "3. In Dokploy dashboard:"
echo "   - Create new project"
echo "   - Connect your Git repository"
echo "   - Use dokploy.yml configuration"
echo "   - Set environment variables"
echo "   - Deploy!"
echo ""
echo "🔗 Useful files created:"
echo "   - dokploy.yml (Dokploy configuration)"
echo "   - Dockerfile.production (Production Dockerfile)"
echo "   - DOKPLOY_DEPLOYMENT.md (Detailed deployment guide)"
echo "   - .env.example (Environment variables template)"
echo ""
echo "🎉 Ready for Dokploy deployment!"
