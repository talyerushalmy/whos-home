#!/bin/bash

# Who's Home Installation Script for Linux
# This script installs and configures the Who's Home LAN device tracker

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
PORT=5000

echo -e "${BLUE}Who's Home - LAN Device Tracker Installation${NC}"
echo "=============================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run this script as root (use sudo)${NC}"
    exit 1
fi

# Update package lists and install dependencies
echo -e "${YELLOW}Installing system dependencies...${NC}"

# Try different package managers until one works
if command -v apt-get &> /dev/null; then
    echo -e "${GREEN}Using apt package manager${NC}"
    apt-get update
    apt-get install -y python3 python3-pip python3-venv git sqlite3 iputils-ping net-tools arping
elif command -v dnf &> /dev/null; then
    echo -e "${GREEN}Using dnf package manager${NC}"
    dnf install -y python3 python3-pip git sqlite iputils net-tools arping
elif command -v yum &> /dev/null; then
    echo -e "${GREEN}Using yum package manager${NC}"
    yum install -y python3 python3-pip git sqlite iputils net-tools arping
elif command -v pacman &> /dev/null; then
    echo -e "${GREEN}Using pacman package manager${NC}"
    pacman -Sy --noconfirm python python-pip git sqlite iputils net-tools arping
elif command -v zypper &> /dev/null; then
    echo -e "${GREEN}Using zypper package manager${NC}"
    zypper install -y python3 python3-pip git sqlite3 iputils net-tools arping
else
    echo -e "${YELLOW}No recognized package manager found${NC}"
    echo -e "${YELLOW}Please manually install: python3 python3-pip git sqlite3 iputils-ping net-tools arping${NC}"
    echo "Continuing anyway..."
fi

# Create service user
echo -e "${YELLOW}Creating service user...${NC}"
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --shell /bin/false --home-dir $INSTALL_DIR --create-home $SERVICE_USER
    echo -e "${GREEN}Created user: $SERVICE_USER${NC}"
else
    echo -e "${YELLOW}User $SERVICE_USER already exists${NC}"
fi

# Store current project directory before changing directories
PROJECT_DIR="$(pwd)"

# Check if we're in the project directory
if [ ! -f "$PROJECT_DIR/app.py" ] || [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
    echo -e "${RED}Error: Missing required files (app.py, requirements.txt)${NC}"
    echo "Current directory: $PROJECT_DIR"
    echo "Please run this script from the project directory containing these files"
    echo "Files found:"
    ls -la "$PROJECT_DIR"
    exit 1
fi

# Create installation directory
echo -e "${YELLOW}Setting up installation directory...${NC}"
mkdir -p $INSTALL_DIR

# Copy application files
echo -e "${YELLOW}Copying application files...${NC}"
echo "Copying from: $PROJECT_DIR"
echo "Copying to: $INSTALL_DIR"

# Copy files from project directory to installation directory
cp -r "$PROJECT_DIR"/* "$INSTALL_DIR/" 2>/dev/null || true
cp "$PROJECT_DIR"/.[^.]* "$INSTALL_DIR/" 2>/dev/null || true

# Change to installation directory
cd $INSTALL_DIR

# Remove unnecessary files from installation
rm -rf .git .gitignore install.sh uninstall.sh 2>/dev/null || true

# Create Python virtual environment
echo -e "${YELLOW}Creating Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Create data directory
echo -e "${YELLOW}Creating data directory...${NC}"
mkdir -p data
chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR

# Create environment file
echo -e "${YELLOW}Creating environment configuration...${NC}"
cat > .env << EOF
# Who's Home Configuration
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
HOST=0.0.0.0
PORT=$PORT
DATABASE_PATH=data/whos_home.db
EOF

# Create startup scripts (universal approach)
echo -e "${YELLOW}Creating startup scripts...${NC}"

# Create start script
cat > /usr/local/bin/whos-home-start << 'EOF'
#!/bin/bash
INSTALL_DIR="/opt/whos-home"
SERVICE_USER="whos-home"
PID_FILE="$INSTALL_DIR/whos-home.pid"

echo "Starting Who's Home..."

# Check if already running
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Who's Home is already running (PID: $(cat "$PID_FILE"))"
    exit 1
fi

# Remove stale PID file
rm -f "$PID_FILE"

# Change to installation directory
cd "$INSTALL_DIR"

# Initialize database if needed
echo "Checking database..."
sudo -u "$SERVICE_USER" bash -c "
    source venv/bin/activate
    python -c 'from src.database import DatabaseManager; db = DatabaseManager(); db.initialize()' 2>/dev/null || true
"

# Start the application
echo "Starting application..."
sudo -u "$SERVICE_USER" bash -c "
    cd '$INSTALL_DIR'
    source venv/bin/activate
    nohup python app.py > /var/log/whos-home.log 2>&1 &
    echo \$! > '$PID_FILE'
"

sleep 2

# Check if started successfully
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Who's Home started successfully (PID: $(cat "$PID_FILE"))"
    echo "Access at: http://$(hostname -I | awk '{print $1}' 2>/dev/null || echo 'localhost'):5000"
else
    echo "Failed to start Who's Home"
    exit 1
fi
EOF

# Create stop script
cat > /usr/local/bin/whos-home-stop << 'EOF'
#!/bin/bash
INSTALL_DIR="/opt/whos-home"
PID_FILE="$INSTALL_DIR/whos-home.pid"

echo "Stopping Who's Home..."

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping process $PID..."
        kill "$PID"
        sleep 2
        
        if kill -0 "$PID" 2>/dev/null; then
            echo "Force stopping..."
            kill -9 "$PID"
        fi
        
        echo "Who's Home stopped."
    else
        echo "Process not running, cleaning up PID file..."
    fi
    rm -f "$PID_FILE"
else
    # Fallback: find by process name
    if pgrep -f "python.*app.py" > /dev/null; then
        echo "Found running process, stopping..."
        pkill -f "python.*app.py"
        echo "Who's Home stopped."
    else
        echo "Who's Home is not running."
    fi
fi
EOF

# Create status script
cat > /usr/local/bin/whos-home-status << 'EOF'
#!/bin/bash
INSTALL_DIR="/opt/whos-home"
PID_FILE="$INSTALL_DIR/whos-home.pid"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    PID=$(cat "$PID_FILE")
    echo "Who's Home is running (PID: $PID)"
    echo "Web interface: http://$(hostname -I | awk '{print $1}' 2>/dev/null || echo 'localhost'):5000"
    echo "Log file: /var/log/whos-home.log"
elif pgrep -f "python.*app.py" > /dev/null; then
    PID=$(pgrep -f "python.*app.py")
    echo "Who's Home is running (PID: $PID) but PID file is missing"
else
    echo "Who's Home is not running."
fi
EOF

# Make scripts executable
chmod +x /usr/local/bin/whos-home-start
chmod +x /usr/local/bin/whos-home-stop  
chmod +x /usr/local/bin/whos-home-status

# Set proper permissions
chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR
chmod 755 $INSTALL_DIR

# Create log file
touch /var/log/whos-home.log
chown $SERVICE_USER:$SERVICE_USER /var/log/whos-home.log

# Try to create systemd service if actually available and working
if command -v systemctl &> /dev/null && [ -d /etc/systemd/system ] && systemctl --version &> /dev/null; then
    # Test if systemd is actually running (not just installed)
    if systemctl is-system-running &> /dev/null || systemctl status &> /dev/null; then
        echo -e "${YELLOW}Creating systemd service...${NC}"
        cat > /etc/systemd/system/whos-home.service << EOF
[Unit]
Description=Who's Home - LAN Device Tracker
After=network.target

[Service]
Type=forking
User=root
ExecStart=/usr/local/bin/whos-home-start
ExecStop=/usr/local/bin/whos-home-stop
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        if systemctl daemon-reload 2>/dev/null && systemctl enable whos-home.service 2>/dev/null; then
            echo -e "${GREEN}Systemd service created and enabled${NC}"
        else
            echo -e "${YELLOW}Systemd service created but not enabled${NC}"
        fi
    else
        echo -e "${YELLOW}Systemd not running, using manual startup${NC}"
    fi
else
    echo -e "${YELLOW}Using manual startup scripts${NC}"
fi

# Start the service
echo -e "${YELLOW}Starting Who's Home...${NC}"
/usr/local/bin/whos-home-start

# Configure firewall (if ufw is available)
if command -v ufw &> /dev/null; then
    echo -e "${YELLOW}Configuring firewall...${NC}"
    ufw allow $PORT/tcp
fi

# Wait for service to start
sleep 3

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo 'localhost')

# Check service status using our universal status script
if /usr/local/bin/whos-home-status | grep -q "running"; then
    echo -e "${GREEN}"
    echo "=============================================="
    echo "Installation completed successfully!"
    echo "=============================================="
    echo -e "${NC}"
    echo "Service Status: Running"
    echo "Web Interface: http://$SERVER_IP:$PORT"
    echo "Default Login: admin / admin"
    echo ""
    echo "Management commands:"
    echo "  Start service:   sudo whos-home-start"
    echo "  Stop service:    sudo whos-home-stop"
    echo "  Check status:    sudo whos-home-status"
    echo "  View logs:       tail -f /var/log/whos-home.log"
    echo ""
    if command -v systemctl &> /dev/null && systemctl --version &> /dev/null 2>&1; then
        echo "Systemd commands (if available):"
        echo "  Start:   sudo systemctl start whos-home"
        echo "  Stop:    sudo systemctl stop whos-home"
        echo "  Status:  sudo systemctl status whos-home"
        echo ""
    fi
    echo -e "${YELLOW}Important Security Notes:${NC}"
    echo "1. Change the default admin password immediately"
    echo "2. Consider setting up a reverse proxy with SSL"
    echo "3. Configure your firewall appropriately"
    echo ""
    echo -e "${GREEN}Installation directory: $INSTALL_DIR${NC}"
else
    echo -e "${RED}✗ Service failed to start${NC}"
    echo "Check status: sudo whos-home-status"
    echo "Check logs: tail -f /var/log/whos-home.log"
    exit 1
fi
