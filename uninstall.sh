#!/bin/bash

# Who's Home Uninstallation Script for Linux
# This script completely removes Who's Home and all its components

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
SERVICE_NAME="whos-home.service"

echo -e "${BLUE}Who's Home - Uninstaller${NC}"
echo "=========================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run this script as root (use sudo)${NC}"
    exit 1
fi

# Confirmation prompt
echo -e "${YELLOW}WARNING: This will completely remove Who's Home and ALL data!${NC}"
echo "This includes:"
echo "- The service and all configuration"
echo "- All tracked device data"
echo "- User accounts and settings" 
echo "- Log files"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " -r
if [[ ! $REPLY =~ ^yes$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

echo -e "${YELLOW}Starting uninstallation...${NC}"

# Stop and disable service
echo -e "${YELLOW}Stopping Who's Home service...${NC}"
if systemctl is-active --quiet $SERVICE_NAME; then
    systemctl stop $SERVICE_NAME
    echo -e "${GREEN}✓ Service stopped${NC}"
else
    echo -e "${YELLOW}Service was not running${NC}"
fi

if systemctl is-enabled --quiet $SERVICE_NAME; then
    systemctl disable $SERVICE_NAME
    echo -e "${GREEN}✓ Service disabled${NC}"
else
    echo -e "${YELLOW}Service was not enabled${NC}"
fi

# Remove systemd service file
echo -e "${YELLOW}Removing systemd service file...${NC}"
if [ -f "/etc/systemd/system/$SERVICE_NAME" ]; then
    rm -f "/etc/systemd/system/$SERVICE_NAME"
    systemctl daemon-reload
    echo -e "${GREEN}✓ Service file removed${NC}"
else
    echo -e "${YELLOW}Service file not found${NC}"
fi

# Remove installation directory
echo -e "${YELLOW}Removing installation directory...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}✓ Installation directory removed${NC}"
else
    echo -e "${YELLOW}Installation directory not found${NC}"
fi

# Remove service user
echo -e "${YELLOW}Removing service user...${NC}"
if id "$SERVICE_USER" &>/dev/null; then
    # Kill any processes owned by the user
    pkill -u "$SERVICE_USER" 2>/dev/null || true
    sleep 2
    
    # Remove user
    userdel "$SERVICE_USER" 2>/dev/null || true
    echo -e "${GREEN}✓ Service user removed${NC}"
else
    echo -e "${YELLOW}Service user not found${NC}"
fi

# Remove firewall rule (if ufw is available)
if command -v ufw &> /dev/null; then
    echo -e "${YELLOW}Removing firewall rules...${NC}"
    ufw delete allow 5000/tcp 2>/dev/null || true
    echo -e "${GREEN}✓ Firewall rules removed${NC}"
fi

# Clean up any remaining files in common locations
echo -e "${YELLOW}Cleaning up remaining files...${NC}"
rm -rf /var/log/whos-home* 2>/dev/null || true
rm -rf /etc/whos-home* 2>/dev/null || true
rm -rf /var/lib/whos-home* 2>/dev/null || true

# Remove python packages (optional - commented out to avoid affecting other apps)
# echo -e "${YELLOW}Removing Python packages...${NC}"
# pip3 uninstall -y flask flask-socketio python-socketio requests scapy psutil python-nmap bcrypt python-dotenv 2>/dev/null || true

echo -e "${GREEN}"
echo "=============================================="
echo "Who's Home has been completely uninstalled!"
echo "=============================================="
echo -e "${NC}"
echo "Removed components:"
echo "✓ System service and configuration"
echo "✓ Installation directory and all data"
echo "✓ Service user account"
echo "✓ Firewall rules"
echo "✓ Log files and temporary data"
echo ""
echo -e "${YELLOW}Note: System packages (Python, etc.) were left installed${NC}"
echo -e "${YELLOW}as they may be used by other applications.${NC}"
echo ""
echo -e "${GREEN}Uninstallation completed successfully!${NC}"
