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
        self.current_version = 3  # Current database schema version
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    def get_connection(self):
        """Get database connection with proper configuration"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_database_version(self):
        """Get current database version"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Check if migrations table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='migrations'
            """)
            
            if not cursor.fetchone():
                return 0  # No migrations table means version 0
            
            # Get the latest migration version
            cursor.execute("""
                SELECT version FROM migrations 
                ORDER BY version DESC 
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"Error getting database version: {e}")
            return 0
        finally:
            conn.close()
    
    def record_migration(self, version, description):
        """Record a successful migration"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO migrations (version, description, applied_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (version, description))
            conn.commit()
            logger.info(f"Recorded migration v{version}: {description}")
        except Exception as e:
            logger.error(f"Error recording migration: {e}")
            raise
        finally:
            conn.close()
    
    def create_migrations_table(self):
        """Create the migrations tracking table"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("Created migrations table")
        except Exception as e:
            logger.error(f"Error creating migrations table: {e}")
            raise
        finally:
            conn.close()
    
    def migrate_to_version_1(self):
        """Initial schema creation"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create tracked_devices table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tracked_devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mac_address TEXT UNIQUE NOT NULL,
                    nickname TEXT,
                    color TEXT DEFAULT '#007bff',
                    is_online BOOLEAN DEFAULT FALSE,
                    last_seen TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create discovery_log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS discovery_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mac_address TEXT,
                    ip_address TEXT,
                    method TEXT,
                    success BOOLEAN,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert default settings
            default_settings = {
                'scan_interval': '30',
                'discovery_methods': '["ping", "arping"]',
                'network_range': 'auto',
                'ping_timeout': '1',
                'arping_timeout': '2'
            }
            
            for key, value in default_settings.items():
                cursor.execute("""
                    INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)
                """, (key, value))
            
            # Create default admin user
            cursor.execute('SELECT COUNT(*) FROM users')
            if cursor.fetchone()[0] == 0:
                from .auth import AuthManager
                auth_manager = AuthManager(None)
                password_hash = auth_manager.hash_password('admin')
                cursor.execute("""
                    INSERT INTO users (username, password_hash) VALUES (?, ?)
                """, ('admin', password_hash))
                logger.info("Created default admin user (username: admin, password: admin)")
            
            conn.commit()
            logger.info("Migration to version 1 completed")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error in migration to version 1: {e}")
            raise
        finally:
            conn.close()
    
    def migrate_to_version_2(self):
        """Add image_path column to tracked_devices"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Check if image_path column exists
            cursor.execute("PRAGMA table_info(tracked_devices)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'image_path' not in columns:
                cursor.execute('ALTER TABLE tracked_devices ADD COLUMN image_path TEXT')
                logger.info("Added image_path column to tracked_devices table")
            
            conn.commit()
            logger.info("Migration to version 2 completed")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error in migration to version 2: {e}")
            raise
        finally:
            conn.close()
    
    def migrate_to_version_3(self):
        """Add TV display public setting"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Add TV display public setting if it doesn't exist
            cursor.execute("""
                INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)
            """, ('tv_display_public', 'true'))
            
            conn.commit()
            logger.info("Migration to version 3 completed")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error in migration to version 3: {e}")
            raise
        finally:
            conn.close()
    
    def run_migrations(self):
        """Run all pending migrations"""
        current_version = self.get_database_version()
        
        if current_version == 0:
            # First time setup - create migrations table
            self.create_migrations_table()
            self.migrate_to_version_1()
            self.record_migration(1, "Initial schema creation")
            current_version = 1
        
        # Run migrations in order
        migrations = [
            (2, "Add image_path column", self.migrate_to_version_2),
            (3, "Add TV display public setting", self.migrate_to_version_3),
        ]
        
        for version, description, migration_func in migrations:
            if current_version < version:
                logger.info(f"Running migration to version {version}: {description}")
                migration_func()
                self.record_migration(version, description)
                current_version = version
        
        if current_version == self.current_version:
            logger.info(f"Database is up to date (version {current_version})")
        else:
            logger.info(f"Database migrated from version {self.get_database_version()} to {self.current_version}")
    
    def initialize(self):
        """Initialize database schema with migrations"""
        with self.lock:
            try:
                self.run_migrations()
                logger.info("Database initialization completed successfully")
            except Exception as e:
                logger.error(f"Error initializing database: {e}")
                raise
    
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
    
    def get_migration_history(self):
        """Get migration history for debugging"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT version, description, applied_at 
                FROM migrations 
                ORDER BY version
            """)
            
            migrations = []
            for row in cursor.fetchall():
                migrations.append({
                    'version': row['version'],
                    'description': row['description'],
                    'applied_at': row['applied_at']
                })
            
            return migrations
        finally:
            conn.close()
    
    def backup_database(self, backup_path=None):
        """Create a backup of the database"""
        if backup_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{self.db_path}.backup_{timestamp}"
        
        import shutil
        try:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Error backing up database: {e}")
            raise
    
    def restore_database(self, backup_path):
        """Restore database from backup"""
        import shutil
        try:
            # Create a backup of current database before restore
            current_backup = self.backup_database()
            logger.info(f"Current database backed up to: {current_backup}")
            
            # Restore from backup
            shutil.copy2(backup_path, self.db_path)
            logger.info(f"Database restored from: {backup_path}")
            
            return True
        except Exception as e:
            logger.error(f"Error restoring database: {e}")
            raise
    
    def export_data(self, export_path):
        """Export database data to JSON for backup/migration"""
        try:
            data = {
                'version': self.get_database_version(),
                'exported_at': datetime.now().isoformat(),
                'users': [],
                'tracked_devices': [],
                'settings': {},
                'migrations': []
            }
            
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Export users
                cursor.execute('SELECT * FROM users')
                for row in cursor.fetchall():
                    data['users'].append(dict(row))
                
                # Export tracked devices
                cursor.execute('SELECT * FROM tracked_devices')
                for row in cursor.fetchall():
                    data['tracked_devices'].append(dict(row))
                
                # Export settings
                cursor.execute('SELECT * FROM settings')
                for row in cursor.fetchall():
                    data['settings'][row['key']] = row['value']
                
                # Export migrations
                cursor.execute('SELECT * FROM migrations')
                for row in cursor.fetchall():
                    data['migrations'].append(dict(row))
                
            finally:
                conn.close()
            
            # Write to file
            with open(export_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.info(f"Database exported to: {export_path}")
            return export_path
            
        except Exception as e:
            logger.error(f"Error exporting database: {e}")
            raise
    
    def import_data(self, import_path):
        """Import database data from JSON backup"""
        try:
            with open(import_path, 'r') as f:
                data = json.load(f)
            
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Clear existing data
                cursor.execute('DELETE FROM users')
                cursor.execute('DELETE FROM tracked_devices')
                cursor.execute('DELETE FROM settings')
                cursor.execute('DELETE FROM migrations')
                
                # Import users
                for user in data.get('users', []):
                    cursor.execute("""
                        INSERT INTO users (username, password_hash, created_at)
                        VALUES (?, ?, ?)
                    """, (user['username'], user['password_hash'], user['created_at']))
                
                # Import tracked devices
                for device in data.get('tracked_devices', []):
                    cursor.execute("""
                        INSERT INTO tracked_devices 
                        (mac_address, nickname, color, image_path, is_online, last_seen, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        device['mac_address'], device['nickname'], device['color'],
                        device.get('image_path'), device['is_online'], device['last_seen'],
                        device['created_at'], device['updated_at']
                    ))
                
                # Import settings
                for key, value in data.get('settings', {}).items():
                    cursor.execute("""
                        INSERT INTO settings (key, value, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    """, (key, value))
                
                # Import migrations
                for migration in data.get('migrations', []):
                    cursor.execute("""
                        INSERT INTO migrations (version, description, applied_at)
                        VALUES (?, ?, ?)
                    """, (migration['version'], migration['description'], migration['applied_at']))
                
                conn.commit()
                logger.info(f"Database imported from: {import_path}")
                
            finally:
                conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error importing database: {e}")
            raise
