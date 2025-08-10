#!/bin/bash

# Who's Home Update Script for Linux
# This script safely updates an existing Who's Home installation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
INSTALL_DIR="/opt/whos-home"
SERVICE_USER="whos-home"
BACKUP_DIR="/opt/whos-home/backups"

echo -e "${BLUE}Who's Home - Update Script${NC}"
echo "============================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run this script as root (use sudo)${NC}"
    exit 1
fi

# Check if installation exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}Who's Home is not installed at $INSTALL_DIR${NC}"
    echo "Please run ./install.sh first for a fresh installation"
    exit 1
fi

# Store current project directory
PROJECT_DIR="$(pwd)"

# Check if we're in the project directory
if [ ! -f "$PROJECT_DIR/app.py" ] || [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
    echo -e "${RED}Error: Missing required files (app.py, requirements.txt)${NC}"
    echo "Please run this script from the project directory"
    exit 1
fi

echo -e "${YELLOW}Starting update process...${NC}"

# Stop the service
echo -e "${YELLOW}Stopping Who's Home service...${NC}"
if [ -f "/usr/local/bin/whos-home-stop" ]; then
    /usr/local/bin/whos-home-stop
    sleep 3
else
    echo -e "${YELLOW}Stop script not found, trying systemctl...${NC}"
    systemctl stop whos-home.service 2>/dev/null || true
    sleep 3
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create timestamp for backup
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_NAME="backup_$TIMESTAMP"

echo -e "${YELLOW}Creating backup of current installation...${NC}"

# Backup current installation (excluding venv and data)
cd "$INSTALL_DIR"
tar -czf "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" \
    --exclude='venv' \
    --exclude='data' \
    --exclude='backups' \
    --exclude='*.pid' \
    --exclude='*.log' \
    .

# Backup database specifically
if [ -f "data/whos_home.db" ]; then
    echo -e "${YELLOW}Creating database backup...${NC}"
    cp "data/whos_home.db" "$BACKUP_DIR/${BACKUP_NAME}_database.db"
fi

echo -e "${GREEN}✓ Backup created: $BACKUP_DIR/${BACKUP_NAME}.tar.gz${NC}"

# Update application files
echo -e "${YELLOW}Updating application files...${NC}"

# Remove old files (excluding preserved directories)
cd "$INSTALL_DIR"
rm -rf app.py src/ templates/ requirements.txt manage_db.py run.py *.py 2>/dev/null || true

# Copy new files from project directory
echo -e "${YELLOW}Copying new application files...${NC}"
cp -r "$PROJECT_DIR"/* "$INSTALL_DIR/" 2>/dev/null || true
cp "$PROJECT_DIR"/.[^.]* "$INSTALL_DIR/" 2>/dev/null || true

# Remove unnecessary files from installation
rm -rf .git .gitignore install.sh uninstall.sh update.sh 2>/dev/null || true

# Update Python dependencies
echo -e "${YELLOW}Updating Python dependencies...${NC}"
cd "$INSTALL_DIR"
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Set proper permissions
chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR

# Run database migration
echo -e "${YELLOW}Running database migrations...${NC}"
sudo -u "$SERVICE_USER" bash -c "
    cd '$INSTALL_DIR'
    source venv/bin/activate
    python -c 'from src.database import DatabaseManager; db = DatabaseManager(); db.initialize()' 2>/dev/null || true
"

# Start the service
echo -e "${YELLOW}Starting Who's Home...${NC}"
if [ -f "/usr/local/bin/whos-home-start" ]; then
    /usr/local/bin/whos-home-start
else
    echo -e "${YELLOW}Start script not found, trying systemctl...${NC}"
    systemctl start whos-home.service 2>/dev/null || true
fi

# Wait for service to start
sleep 5

# Check service status
if [ -f "/usr/local/bin/whos-home-status" ]; then
    STATUS_OUTPUT=$(/usr/local/bin/whos-home-status)
    if echo "$STATUS_OUTPUT" | grep -q "running"; then
        echo -e "${GREEN}"
        echo "=============================================="
        echo "Update completed successfully!"
        echo "=============================================="
        echo -e "${NC}"
        echo "Service Status: Running"
        echo "Web Interface: http://$(hostname -I | awk '{print $1}' 2>/dev/null || echo 'localhost'):5000"
        echo ""
        echo "Backup created: $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
        echo "Database backup: $BACKUP_DIR/${BACKUP_NAME}_database.db"
        echo ""
        echo -e "${YELLOW}If you encounter any issues, you can restore from backup:${NC}"
        echo "1. Stop the service: sudo whos-home-stop"
        echo "2. Restore files: cd $INSTALL_DIR && tar -xzf $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
        echo "3. Restore database: cp $BACKUP_DIR/${BACKUP_NAME}_database.db data/whos_home.db"
        echo "4. Start service: sudo whos-home-start"
    else
        echo -e "${RED}✗ Service failed to start after update${NC}"
        echo "Check status: sudo whos-home-status"
        echo "Check logs: tail -f /var/log/whos-home.log"
        exit 1
    fi
else
    echo -e "${YELLOW}Status script not found, checking if service is running...${NC}"
    if pgrep -f "python.*app.py" > /dev/null; then
        echo -e "${GREEN}✓ Update completed successfully!${NC}"
    else
        echo -e "${RED}✗ Service may not be running${NC}"
        echo "Check manually: sudo whos-home-status"
    fi
fi
