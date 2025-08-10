#!/usr/bin/env python3
"""
Database management tool for Who's Home
Provides command-line interface for database operations
"""

import argparse
import sys
import os
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import DatabaseManager

def main():
    parser = argparse.ArgumentParser(description='Who\'s Home Database Management Tool')
    parser.add_argument('--db-path', default='data/whos_home.db', 
                       help='Path to the database file (default: data/whos_home.db)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show database status')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create database backup')
    backup_parser.add_argument('--output', help='Output path for backup file')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore database from backup')
    restore_parser.add_argument('backup_path', help='Path to backup file')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export database to JSON')
    export_parser.add_argument('--output', help='Output path for JSON file')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import database from JSON')
    import_parser.add_argument('json_path', help='Path to JSON file')
    
    # Migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Run database migrations')
    
    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset database (WARNING: This will delete all data!)')
    reset_parser.add_argument('--confirm', action='store_true', 
                             help='Confirm that you want to reset the database')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize database manager
    db_manager = DatabaseManager(args.db_path)
    
    try:
        if args.command == 'status':
            show_status(db_manager)
        elif args.command == 'backup':
            create_backup(db_manager, args.output)
        elif args.command == 'restore':
            restore_backup(db_manager, args.backup_path)
        elif args.command == 'export':
            export_database(db_manager, args.output)
        elif args.command == 'import':
            import_database(db_manager, args.json_path)
        elif args.command == 'migrate':
            run_migrations(db_manager)
        elif args.command == 'reset':
            reset_database(db_manager, args.confirm)
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def show_status(db_manager):
    """Show database status"""
    print("=== Who's Home Database Status ===")
    
    current_version = db_manager.get_database_version()
    latest_version = db_manager.current_version
    
    print(f"Database Path: {db_manager.db_path}")
    print(f"Current Version: {current_version}")
    print(f"Latest Version: {latest_version}")
    print(f"Status: {'Up to date' if current_version == latest_version else 'Needs migration'}")
    
    if current_version > 0:
        print("\nMigration History:")
        migrations = db_manager.get_migration_history()
        for migration in migrations:
            print(f"  v{migration['version']}: {migration['description']} ({migration['applied_at']})")

def create_backup(db_manager, output_path):
    """Create database backup"""
    print("Creating database backup...")
    backup_path = db_manager.backup_database(output_path)
    print(f"Backup created: {backup_path}")

def restore_backup(db_manager, backup_path):
    """Restore database from backup"""
    if not os.path.exists(backup_path):
        print(f"Error: Backup file not found: {backup_path}")
        return
    
    print(f"Restoring database from: {backup_path}")
    confirm = input("This will overwrite the current database. Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("Restore cancelled.")
        return
    
    db_manager.restore_database(backup_path)
    print("Database restored successfully.")

def export_database(db_manager, output_path):
    """Export database to JSON"""
    if not output_path:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"data/export_{timestamp}.json"
    
    print(f"Exporting database to: {output_path}")
    export_path = db_manager.export_data(output_path)
    print(f"Database exported: {export_path}")

def import_database(db_manager, json_path):
    """Import database from JSON"""
    if not os.path.exists(json_path):
        print(f"Error: JSON file not found: {json_path}")
        return
    
    print(f"Importing database from: {json_path}")
    confirm = input("This will overwrite the current database. Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("Import cancelled.")
        return
    
    db_manager.import_data(json_path)
    print("Database imported successfully.")

def run_migrations(db_manager):
    """Run database migrations"""
    print("Running database migrations...")
    db_manager.run_migrations()
    print("Migrations completed successfully.")

def reset_database(db_manager, confirmed):
    """Reset database"""
    if not confirmed:
        print("WARNING: This will delete ALL data from the database!")
        confirm = input("Type 'RESET' to confirm: ")
        if confirm != 'RESET':
            print("Reset cancelled.")
            return
    
    print("Resetting database...")
    
    # Remove the database file
    if os.path.exists(db_manager.db_path):
        os.remove(db_manager.db_path)
        print(f"Deleted database file: {db_manager.db_path}")
    
    # Reinitialize with fresh schema
    db_manager.initialize()
    print("Database reset and reinitialized successfully.")

if __name__ == '__main__':
    main()
