# Who's Home - LAN Device Tracker

A web-based application that tracks which flatmates/family members are home by monitoring their devices on the local network. Perfect for knowing who's around without having to shout!

![Dashboard Screenshot](https://img.shields.io/badge/Python-3.7+-blue) ![License](https://img.shields.io/badge/License-MIT-green)

## Features

- 🏠 **Real-time device tracking** - Know who's home instantly
- 🌐 **Web dashboard** - Beautiful, responsive interface
- 📺 **TV display mode** - Full-screen view perfect for wall-mounted displays
- 🎨 **Color-coded devices** - Each person gets a unique color
- ✏️ **Device editing** - Change nicknames and colors after setup
- 📸 **Profile pictures** - Upload custom photos or use default emoji
- 🔍 **Multiple discovery methods** - Ping, ARP ping, and more
- ⚙️ **Configurable settings** - Scan intervals, network ranges, timeouts
- 📱 **Device management** - Add/remove devices, set nicknames
- 🔐 **Authentication** - Secure login system
- 📊 **Real-time updates** - Live status updates via WebSocket
- 💾 **SQLite database** - Persistent storage for all settings
- 🌍 **Universal compatibility** - Works on any Linux system

## How It Works

The application uses various network discovery methods to detect devices:

1. **Ping (ICMP)** - Fast and reliable for most devices
2. **ARP Ping** - Works even when devices block ICMP
3. **ARP Table Lookup** - Checks system ARP cache

You can track devices by their MAC addresses and assign friendly nicknames and colors for easy identification.

## Quick Start

### Installation

For any Linux computer on your LAN (Raspberry Pi, Ubuntu, Debian, CentOS, etc):

```bash
git clone https://github.com/talyerushalmy/whos-home.git
cd whos-home
sudo ./install.sh
```



### Post-Installation

1. Access the web interface at `http://your-device-ip:5000`
2. Login with default credentials: `admin` / `admin`
3. **Change the password immediately!**
4. Configure your network range in Settings if auto-detection is wrong
5. Click "Add Device" to discover and start tracking devices
6. For TV display: Click "TV Display" or visit `/tv` for full-screen mode

### Manual Installation

#### Prerequisites

- Linux server (Debian/Ubuntu/CentOS/RHEL/Fedora)
- Python 3.7 or higher
- Root or sudo access

#### Install Dependencies

**Debian/Ubuntu:**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git sqlite3 iputils-ping net-tools arping
```

**CentOS/RHEL/Fedora:**
```bash
sudo dnf install python3 python3-pip git sqlite iputils net-tools arping
```

#### Setup Application

1. Clone and setup:
```bash
git clone https://github.com/talyerushalmy/whos-home.git
cd whos-home
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Create data directory:
```bash
mkdir data
```

3. Run the application:
```bash
python app.py
```

4. Access at `http://localhost:5000`

## Configuration

### Environment Variables

Create a `.env` file from the example:

```bash
cp env.example .env
# Edit .env and change the SECRET_KEY to a secure random value
```

### Discovery Settings

Configure through the web interface:

- **Scan Interval**: How often to check device status (10-300 seconds)
- **Network Range**: IP range to scan (e.g., `192.168.1.0/24` or `auto`)
- **Discovery Methods**: Choose between ping, arping, or both
- **Timeouts**: Adjust for your network conditions

### Database

The application uses SQLite with automatic schema creation. The database stores:

- User accounts
- Tracked devices (MAC, nickname, color)
- Discovery settings
- Discovery logs for debugging

## Usage

### Adding Devices

1. Click "Add Device" on the dashboard
2. Run network discovery to find devices
3. Select devices to track and assign nicknames
4. Choose colors for easy identification

### Managing Devices

- **Add**: Discover devices on your network and add them to tracking
- **Edit**: Change device nicknames, colors, and profile pictures
- **Pictures**: Upload custom photos or remove to use default 👤 emoji
- **Remove**: Stop tracking a device
- **Status**: View online/offline status and last seen time
- **Colors**: Each device gets a unique color for easy identification

### Settings

Access via the gear icon in the dashboard:

- **Scan Interval**: How often to check device status (10-300 seconds)
- **Network Range**: IP range to scan (auto-detected or manual)
- **Discovery Methods**: Choose ping, ARP ping, or both
- **Timeouts**: Adjust ping and ARP timeouts for your network
- **TV Display Access**: Choose whether the TV display requires authentication or is publicly accessible

### TV Display Mode

Perfect for wall-mounted displays or tablets:

- **Full-screen layout** optimized for viewing from a distance
- **Dynamic columns** - one per person currently home
- **Real-time updates** - automatically refreshes as people come/go
- **Color-coded** - each person shown in their chosen color
- **Smart text contrast** - readable on any background color
- **Configurable access**: Choose between public access or authentication required in Settings
- **Access**: Click "TV Display" in navigation or visit `/tv`

## Service Management

```bash
# Service management (works on all systems)
sudo whos-home-start
sudo whos-home-stop
sudo whos-home-status

# View logs
tail -f /var/log/whos-home.log

# If systemd is available, you can also use:
sudo systemctl start whos-home
sudo systemctl stop whos-home
sudo systemctl status whos-home
```

## Hardware Requirements

**Any Linux computer directly connected to your LAN:**

- Raspberry Pi (any model) - Perfect for dedicated use
- Desktop PC with Linux
- Laptop with Linux  
- Mini PC/NUC
- Old computer repurposed with Linux
- Any device with Ethernet or WiFi connection to your network

**Network requirements:**
- Must be on the same LAN as devices you want to track
- Needs network scanning capabilities (ping, ARP)
- For best MAC detection: direct network access (not virtualized)

**Supported Linux distributions:**
- Ubuntu/Debian (apt)
- CentOS/RHEL/Fedora (dnf/yum)
- Arch Linux (pacman)
- openSUSE (zypper)
- Any distribution with Python 3.7+

## Security Considerations

1. **Change default password** immediately after installation
2. **Use HTTPS** in production (Raspberry Pi installer includes nginx)
3. **Firewall**: Only allow access from trusted networks
4. **Regular updates**: Keep dependencies updated
5. **Network access**: The service needs raw network access for best MAC detection
6. **Placement**: Install on a device with direct network access (not virtualized)

## Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check status and logs
sudo whos-home-status
tail -f /var/log/whos-home.log

# Check permissions
sudo chown -R whos-home:whos-home /opt/whos-home
```

**No devices found:**
- Check network range settings match your LAN
- Ensure devices are powered on and connected
- Try different discovery methods in settings

**MAC addresses show "Unknown":**
- Normal on some networks, devices will still be tracked by IP
- Ensure the computer is on the same LAN segment

### Database Management

The application includes a comprehensive database migration system that automatically updates your database schema when you update the application.

#### Automatic Migrations

- **Seamless updates**: Your data is preserved when updating the application
- **Version tracking**: Database schema version is tracked and updated automatically
- **Safe migrations**: Each migration is tested and applied safely

#### Manual Database Operations

Use the built-in database management tool:

```bash
# Check database status
python manage_db.py status

# Create a backup
python manage_db.py backup

# Export data to JSON
python manage_db.py export

# Run migrations manually
python manage_db.py migrate

# Reset database (WARNING: deletes all data)
python manage_db.py reset --confirm
```

#### Web Interface

Access database management through the Settings page:
- **Database Status**: View current version and migration history
- **Create Backup**: Generate database backup files
- **Export Data**: Export to JSON format for portability

#### Database Issues

**Reset database (will lose all data):**
```bash
# Using the management tool (recommended)
python manage_db.py reset --confirm

# Manual reset
sudo systemctl stop whos-home
sudo rm /opt/whos-home/data/whos_home.db
sudo systemctl start whos-home
```

**Backup before updates:**
```bash
# Create backup before updating
python manage_db.py backup

# Update application
git pull
sudo systemctl restart whos-home
```

## File Structure

```
whos-home/
├── app.py                 # Main application
├── requirements.txt       # Python dependencies
├── install.sh            # Installation script
├── src/
│   ├── __init__.py
│   ├── auth.py           # Authentication
│   ├── database.py       # Database management
│   └── discovery.py      # Device discovery
├── templates/
│   ├── base.html         # Base template
│   ├── login.html        # Login page
│   └── dashboard.html    # Main dashboard
└── data/
    └── whos_home.db      # SQLite database (created automatically)
```

## API Endpoints

- `GET /` - Dashboard (requires auth)
- `GET /tv` - TV display mode (auth configurable via settings)
- `GET /api/devices` - Get tracked devices (auth configurable via settings)
- `GET /login` - Login page
- `POST /login` - Authenticate user
- `GET /logout` - Logout
- `GET /api/devices` - Get tracked devices
- `GET /api/discover` - Discover network devices
- `POST /api/track_device` - Add device to tracking
- `POST /api/update_device` - Update device nickname/color
- `POST /api/untrack_device` - Remove device from tracking
- `GET /api/settings` - Get settings
- `POST /api/settings` - Update settings
- `GET /api/database/status` - Get database status and migration info
- `POST /api/database/backup` - Create database backup
- `POST /api/database/export` - Export database to JSON

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with Flask and Socket.IO
- Uses Bootstrap for UI
- Thanks to the open-source community

## Support

If you encounter issues:

1. Check the troubleshooting section
2. Look at existing GitHub issues
3. Create a new issue with:
   - Your OS and version
   - Error messages/logs
   - Steps to reproduce

---

**Note**: This application requires network scanning capabilities and works best on physical Linux systems with direct network access. WSL and virtualized environments have limited MAC address detection capabilities.
