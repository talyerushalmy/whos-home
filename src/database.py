"""
Database manager for Who's Home application
Handles SQLite database operations and schema management
"""

import sqlite3
import logging
import os
import json
from datetime import datetime
import threading

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path='data/whos_home.db'):
        self.db_path = db_path
        self.lock = threading.Lock()
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    def get_connection(self):
        """Get database connection with proper configuration"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def initialize(self):
        """Initialize database schema"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Create users table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create tracked_devices table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tracked_devices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mac_address TEXT UNIQUE NOT NULL,
                        nickname TEXT,
                        color TEXT DEFAULT '#007bff',
                        image_path TEXT,
                        is_online BOOLEAN DEFAULT FALSE,
                        last_seen TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create settings table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create discovery_log table for debugging
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS discovery_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mac_address TEXT,
                        ip_address TEXT,
                        method TEXT,
                        success BOOLEAN,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Insert default settings if not exists
                default_settings = {
                    'scan_interval': '30',
                    'discovery_methods': '["ping", "arping"]',
                    'network_range': 'auto',
                    'ping_timeout': '1',
                    'arping_timeout': '2',
                    'tv_display_public': 'true'
                }
                
                for key, value in default_settings.items():
                    cursor.execute('''
                        INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)
                    ''', (key, value))
                
                # Check if image_path column exists and add it if not (migration)
                cursor.execute("PRAGMA table_info(tracked_devices)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'image_path' not in columns:
                    cursor.execute('ALTER TABLE tracked_devices ADD COLUMN image_path TEXT')
                    logger.info("Added image_path column to tracked_devices table")
                
                # Create default admin user if no users exist
                cursor.execute('SELECT COUNT(*) FROM users')
                if cursor.fetchone()[0] == 0:
                    from .auth import AuthManager
                    auth_manager = AuthManager(None)
                    password_hash = auth_manager.hash_password('admin')
                    cursor.execute('''
                        INSERT INTO users (username, password_hash) VALUES (?, ?)
                    ''', ('admin', password_hash))
                    logger.info("Created default admin user (username: admin, password: admin)")
                
                conn.commit()
                logger.info("Database schema initialized successfully")
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error initializing database: {e}")
                raise
            finally:
                conn.close()
    
    def add_tracked_device(self, mac_address, nickname=None, color='#007bff'):
        """Add a device to the tracking list"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO tracked_devices 
                    (mac_address, nickname, color, updated_at) 
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (mac_address.upper(), nickname, color))
                conn.commit()
                logger.info(f"Added tracked device: {mac_address} ({nickname})")
            except Exception as e:
                conn.rollback()
                logger.error(f"Error adding tracked device: {e}")
                raise
            finally:
                conn.close()
    
    def remove_tracked_device(self, mac_address):
        """Remove a device from the tracking list"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM tracked_devices WHERE mac_address = ?', 
                             (mac_address.upper(),))
                conn.commit()
                logger.info(f"Removed tracked device: {mac_address}")
            except Exception as e:
                conn.rollback()
                logger.error(f"Error removing tracked device: {e}")
                raise
            finally:
                conn.close()
    
    def update_tracked_device(self, mac_address, nickname=None, color=None, image_path=None, update_image=False):
        """Update device nickname, color, and/or image"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Build dynamic update query
                updates = []
                params = []
                
                if nickname is not None:
                    updates.append('nickname = ?')
                    params.append(nickname)
                
                if color is not None:
                    updates.append('color = ?')
                    params.append(color)
                
                # Handle image updates explicitly
                if update_image:
                    updates.append('image_path = ?')
                    params.append(image_path)  # Can be None to clear the field
                
                if updates:
                    updates.append('updated_at = CURRENT_TIMESTAMP')
                    params.append(mac_address.upper())
                    
                    query = f"UPDATE tracked_devices SET {', '.join(updates)} WHERE mac_address = ?"
                    cursor.execute(query, params)
                    conn.commit()
                    logger.info(f"Updated tracked device: {mac_address} (image_path: {image_path})")
            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating tracked device: {e}")
                raise
            finally:
                conn.close()
    
    def get_tracked_devices(self):
        """Get all tracked devices"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT mac_address, nickname, color, image_path, is_online, last_seen, created_at
                FROM tracked_devices 
                ORDER BY nickname, mac_address
            ''')
            
            devices = []
            for row in cursor.fetchall():
                devices.append({
                    'mac_address': row['mac_address'],
                    'nickname': row['nickname'],
                    'color': row['color'],
                    'image_path': row['image_path'],
                    'is_online': bool(row['is_online']),
                    'last_seen': row['last_seen'],
                    'created_at': row['created_at']
                })
            
            return devices
        finally:
            conn.close()
    
    def update_device_status(self, mac_address, is_online):
        """Update device online status"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                last_seen = datetime.now().isoformat() if is_online else None
                cursor.execute('''
                    UPDATE tracked_devices 
                    SET is_online = ?, last_seen = COALESCE(?, last_seen), updated_at = CURRENT_TIMESTAMP
                    WHERE mac_address = ?
                ''', (is_online, last_seen, mac_address.upper()))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating device status: {e}")
                raise
            finally:
                conn.close()
    
    def get_settings(self):
        """Get all settings as a dictionary"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT key, value FROM settings')
            
            settings = {}
            for row in cursor.fetchall():
                key = row['key']
                value = row['value']
                
                # Try to parse JSON values
                try:
                    if value.startswith('[') or value.startswith('{'):
                        value = json.loads(value)
                    elif value.isdigit():
                        value = int(value)
                    elif value.replace('.', '').isdigit():
                        value = float(value)
                except (json.JSONDecodeError, ValueError):
                    pass  # Keep as string
                
                settings[key] = value
            
            return settings
        finally:
            conn.close()
    
    def update_settings(self, settings_dict):
        """Update multiple settings"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                for key, value in settings_dict.items():
                    # Convert complex types to JSON
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    else:
                        value = str(value)
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO settings (key, value, updated_at) 
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    ''', (key, value))
                
                conn.commit()
                logger.info(f"Updated settings: {list(settings_dict.keys())}")
            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating settings: {e}")
                raise
            finally:
                conn.close()
    
    def log_discovery(self, mac_address, ip_address, method, success):
        """Log discovery attempt for debugging"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO discovery_log (mac_address, ip_address, method, success)
                    VALUES (?, ?, ?, ?)
                ''', (mac_address, ip_address, method, success))
                conn.commit()
            except Exception as e:
                logger.error(f"Error logging discovery: {e}")
            finally:
                conn.close()
    
    def get_user_by_username(self, username):
        """Get user by username"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
