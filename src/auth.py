"""
Authentication manager for Who's Home application
Handles user authentication and session management
"""

import bcrypt
import logging

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False
    
    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify user credentials"""
        if not self.db_manager:
            return False
        
        user = self.db_manager.get_user_by_username(username)
        if not user:
            return False
        
        return self.verify_password(password, user['password_hash'])
    
    def create_user(self, username: str, password: str) -> bool:
        """Create a new user"""
        if not self.db_manager:
            return False
        
        try:
            password_hash = self.hash_password(password)
            # Implementation would need to be added to database.py
            # self.db_manager.create_user(username, password_hash)
            return True
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return False
