#!/bin/bash

# Dokploy Deployment Script
# This script helps prepare your app for Dokploy deployment

echo "🚀 Preparing Website Monitoring App for Dokploy Deployment..."

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

echo "✅ Found main.py - we're in the right directory"

# Create .dockerignore if it doesn't exist
if [ ! -f ".dockerignore" ]; then
    echo "📝 Creating .dockerignore file..."
    cat > .dockerignore << EOF
# Git
.git
.gitignore

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env
pip-log.txt
pip-delete-this-directory.txt
.tox
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.git
.mypy_cache
.pytest_cache
.hypothesis

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# IDE
.vscode
.idea
*.swp
*.swo
*~

# Project specific
@Files Not Need Now/
docs/
tests/
*.md
!README.md
!DEPLOYMENT_GUIDE.md
!DOKPLOY_DEPLOYMENT.md

# Logs
*.log
logs/

# Data (will be mounted as volume)
data/snapshots/
data/*.log
EOF
    echo "✅ Created .dockerignore"
else
    echo "✅ .dockerignore already exists"
fi

# Check if Dockerfile exists
if [ ! -f "Dockerfile" ]; then
    echo "❌ Error: Dockerfile not found. Please create one first."
    exit 1
fi

echo "✅ Dockerfile found"

# Check if dokploy.yml exists
if [ ! -f "dokploy.yml" ]; then
    echo "❌ Error: dokploy.yml not found. Please create one first."
    exit 1
fi

echo "✅ dokploy.yml found"

# Create a simple health check endpoint
echo "🔍 Checking if health endpoint exists..."
if ! grep -q "def health" src/app.py; then
    echo "📝 Adding health check endpoint..."
    cat >> src/app.py << 'EOF'

@app.route('/health')
def health():
    """Health check endpoint for Dokploy."""
    try:
        # Check if database is accessible
        from src.website_manager_sqlite import WebsiteManagerSQLite
        wm = WebsiteManagerSQLite()
        websites = wm.list_websites()
        
        return {
            'status': 'healthy',
            'websites_count': len(websites),
            'scheduler_enabled': os.getenv('SCHEDULER_ENABLED', 'false').lower() == 'true'
        }, 200
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }, 500
EOF
    echo "✅ Added health check endpoint"
else
    echo "✅ Health check endpoint already exists"
fi

echo ""
echo "🎉 Preparation complete! Your app is ready for Dokploy deployment."
echo ""
echo "📋 Next steps:"
echo "1. Push your code to a Git repository (GitHub/GitLab)"
echo "2. Access your Dokploy dashboard at http://your-vps-ip:3000"
echo "3. Create a new project and select 'Docker Compose'"
echo "4. Connect your Git repository or upload the code"
echo "5. Configure environment variables (see DOKPLOY_DEPLOYMENT.md)"
echo "6. Deploy!"
echo ""
echo "📖 For detailed instructions, see DOKPLOY_DEPLOYMENT.md"