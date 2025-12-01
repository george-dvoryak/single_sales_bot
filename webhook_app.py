# webhook_app.py
"""
WSGI application for PythonAnywhere or other WSGI servers.
This file simply imports and exposes the Flask application from main.py
"""

import sys
import traceback

try:
    from main import application
    print("✅ Successfully imported application from main.py")
except Exception as e:
    print(f"❌ ERROR importing application from main.py: {e}")
    traceback.print_exc()
    # Create a minimal Flask app that shows the error
    from flask import Flask
    application = Flask(__name__)
    
    @application.route("/")
    def error():
        return f"Error loading application: {str(e)}", 500

# This is the WSGI application that PythonAnywhere will use
# In PythonAnywhere Web tab, set:
# - Source code: /home/yourusername/single_sales_bot
# - WSGI configuration file should import: from webhook_app import application
