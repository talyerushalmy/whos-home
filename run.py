#!/usr/bin/env python3
"""
Development server runner for Who's Home
Use this for development instead of app.py for better debugging
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    from app import app, socketio
    
    # Development settings
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    
    print(f"Starting Who's Home development server on {host}:{port}")
    print(f"Debug mode: {debug}")
    print("Access the application at: http://{}:{}".format(host, port))
    
    # Run with development settings
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
