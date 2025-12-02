# webhook_app.py
"""
WSGI application for PythonAnywhere or other WSGI servers.
This file simply imports and exposes the Flask application from main.py
"""

import traceback

try:
    print("[webhook_app] Starting import of main module...")
    from main import application
    print("[webhook_app] ✅ Successfully imported application from main.py")
except Exception as e:
    print(f"[webhook_app] ❌ ERROR importing application from main.py: {e}")
    traceback.print_exc()
    
    # Create a minimal Flask app that shows the error on all routes
    from flask import Flask
    application = Flask(__name__)
    
    error_msg = f"Error loading application: {str(e)}\n\n{traceback.format_exc()}"
    
    @application.route("/")
    def error_root():
        return error_msg, 500
    
    @application.route("/prodamus_webhook", methods=["GET", "POST"])
    def error_prodamus():
        return error_msg, 500
    
    @application.route("/diag")
    def error_diag():
        return error_msg, 500

# This is the WSGI application that PythonAnywhere will use
# In PythonAnywhere Web tab, set:
# - Source code: /home/yourusername/single_sales_bot
# - WSGI configuration file should import: from webhook_app import application
