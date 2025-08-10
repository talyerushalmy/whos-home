#!/usr/bin/env python3
"""
Who's Home - LAN Device Tracker
A web application to track who's home based on device presence on the LAN.
"""

import os
import sys
import logging
import uuid
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import sqlite3
import threading
import time
import json
from datetime import datetime

from src.database import DatabaseManager
from src.discovery import DeviceDiscovery
from src.auth import AuthManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize managers
db_manager = DatabaseManager()
device_discovery = DeviceDiscovery(db_manager)
auth_manager = AuthManager(db_manager)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_device_image(file, mac_address):
    """Save uploaded device image and return the path"""
    if file and allowed_file(file.filename):
        # Generate unique filename with MAC address prefix
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{mac_address.replace(':', '-')}_{uuid.uuid4().hex[:8]}.{file_ext}"
        filename = secure_filename(filename)
        
        # Ensure upload directory exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Save file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Return relative path for database storage
        return f"uploads/{filename}"
    return None

# Global state
tracked_devices = {}
discovery_running = False

@app.route('/')
def index():
    """Main dashboard route"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/tv')
def tv_display():
    """TV display route - shows who's home in full screen"""
    # Check if TV display requires authentication
    settings = db_manager.get_settings()
    tv_display_public = settings.get('tv_display_public', True)
    
    # Convert string to boolean if needed
    if isinstance(tv_display_public, str):
        tv_display_public = tv_display_public.lower() == 'true'
    
    # Require authentication if TV display is not public
    if not tv_display_public and not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('tv_display.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.json.get('username')
        password = request.json.get('password')
        
        if auth_manager.verify_credentials(username, password):
            session['logged_in'] = True
            session['username'] = username
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/devices')
def get_devices():
    """Get all tracked devices with their status"""
    # Check if TV display requires authentication
    settings = db_manager.get_settings()
    tv_display_public = settings.get('tv_display_public', True)
    
    # Convert string to boolean if needed
    if isinstance(tv_display_public, str):
        tv_display_public = tv_display_public.lower() == 'true'
    
    # Require authentication if TV display is not public
    if not tv_display_public and not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    devices = db_manager.get_tracked_devices()
    return jsonify({'devices': devices})

@app.route('/api/discover')
def discover_devices():
    """Discover all devices on the network"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    discovered = device_discovery.discover_all_devices()
    return jsonify({'devices': discovered})

@app.route('/api/track_device', methods=['POST'])
def track_device():
    """Add a device to tracking list"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    mac_address = data.get('mac_address')
    nickname = data.get('nickname')
    color = data.get('color', '#007bff')
    
    if not mac_address:
        return jsonify({'error': 'MAC address required'}), 400
    
    db_manager.add_tracked_device(mac_address, nickname, color)
    return jsonify({'success': True})

@app.route('/api/untrack_device', methods=['POST'])
def untrack_device():
    """Remove a device from tracking list"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    mac_address = data.get('mac_address')
    
    if not mac_address:
        return jsonify({'error': 'MAC address required'}), 400
    
    db_manager.remove_tracked_device(mac_address)
    return jsonify({'success': True})

@app.route('/api/update_device', methods=['POST'])
def update_device():
    """Update device nickname, color, and image"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    mac_address = request.form.get('mac_address')
    nickname = request.form.get('nickname')
    color = request.form.get('color')
    
    if not mac_address:
        return jsonify({'error': 'MAC address required'}), 400
    
    if not nickname:
        return jsonify({'error': 'Nickname required'}), 400
    
    # Handle image operations
    image_path = None
    remove_image = request.form.get('remove_image') == 'true'
    
    if remove_image:
        # Get current device to find old image for cleanup
        current_devices = db_manager.get_tracked_devices()
        current_device = next((d for d in current_devices if d['mac_address'] == mac_address.upper()), None)
        if current_device and current_device['image_path']:
            # Delete old image file
            old_file_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(current_device['image_path']))
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
                logger.info(f"Deleted old image file: {old_file_path}")
        image_path = None  # This will clear the image_path in database
        logger.info(f"Removed image for device {mac_address}")
    elif 'image' in request.files:
        file = request.files['image']
        if file.filename:  # File was selected
            # Get current device to clean up old image
            current_devices = db_manager.get_tracked_devices()
            current_device = next((d for d in current_devices if d['mac_address'] == mac_address.upper()), None)
            if current_device and current_device['image_path']:
                # Delete old image file
                old_file_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(current_device['image_path']))
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
                    logger.info(f"Deleted old image file: {old_file_path}")
            
            image_path = save_device_image(file, mac_address)
            if not image_path:
                return jsonify({'error': 'Invalid image file'}), 400
            logger.info(f"Saved device image: {image_path} for {mac_address}")
    
    # Always update image_path when we're handling image operations
    update_image = remove_image or ('image' in request.files and request.files['image'].filename)
    db_manager.update_tracked_device(mac_address, nickname, color, image_path, update_image=update_image)
    logger.info(f"Updated device {mac_address} with image_path: {image_path}, update_image: {update_image}, remove_image: {remove_image}")
    return jsonify({'success': True})

@app.route('/api/settings')
def get_settings():
    """Get discovery settings"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    settings = db_manager.get_settings()
    return jsonify({'settings': settings})

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded device images"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update discovery settings"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    db_manager.update_settings(data)
    device_discovery.update_settings(data)
    return jsonify({'success': True})

@app.route('/api/database/status')
def database_status():
    """Get database status and migration information"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        current_version = db_manager.get_database_version()
        migration_history = db_manager.get_migration_history()
        
        return jsonify({
            'current_version': current_version,
            'latest_version': db_manager.current_version,
            'migration_history': migration_history,
            'needs_migration': current_version < db_manager.current_version
        })
    except Exception as e:
        logger.error(f"Error getting database status: {e}")
        return jsonify({'error': 'Failed to get database status'}), 500

@app.route('/api/database/backup', methods=['POST'])
def backup_database():
    """Create a database backup"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        backup_path = db_manager.backup_database()
        return jsonify({
            'success': True,
            'backup_path': backup_path,
            'message': 'Database backup created successfully'
        })
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return jsonify({'error': 'Failed to create backup'}), 500

@app.route('/api/database/export', methods=['POST'])
def export_database():
    """Export database to JSON"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_path = f"data/export_{timestamp}.json"
        export_path = db_manager.export_data(export_path)
        
        return jsonify({
            'success': True,
            'export_path': export_path,
            'message': 'Database exported successfully'
        })
    except Exception as e:
        logger.error(f"Error exporting database: {e}")
        return jsonify({'error': 'Failed to export database'}), 500

def discovery_worker():
    """Background worker for device discovery"""
    global discovery_running
    
    while discovery_running:
        try:
            # Get tracked devices and check their status
            tracked = db_manager.get_tracked_devices()
            updated_devices = []
            
            for device in tracked:
                is_online = device_discovery.check_device_status(device['mac_address'])
                if is_online != device['is_online']:
                    db_manager.update_device_status(device['mac_address'], is_online)
                    device['is_online'] = is_online
                    device['last_seen'] = datetime.now().isoformat() if is_online else device['last_seen']
                    updated_devices.append(device)
            
            # Emit updates to connected clients
            if updated_devices:
                socketio.emit('device_updates', {'devices': updated_devices})
            
            # Wait before next scan
            settings = db_manager.get_settings()
            scan_interval = settings.get('scan_interval', 30)
            time.sleep(scan_interval)
            
        except Exception as e:
            logger.error(f"Error in discovery worker: {e}")
            time.sleep(10)

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    
    # Send current device status
    devices = db_manager.get_tracked_devices()
    emit('device_updates', {'devices': devices})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

def main():
    """Main application entry point"""
    global discovery_running
    
    try:
        # Initialize database
        db_manager.initialize()
        logger.info("Database initialized successfully")
        
        # Start discovery worker
        discovery_running = True
        discovery_thread = threading.Thread(target=discovery_worker, daemon=True)
        discovery_thread.start()
        logger.info("Device discovery worker started")
        
        # Start web server
        port = int(os.environ.get('PORT', 5000))
        host = os.environ.get('HOST', '0.0.0.0')
        
        logger.info(f"Starting Who's Home server on {host}:{port}")
        socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)
    finally:
        discovery_running = False

if __name__ == '__main__':
    main()
