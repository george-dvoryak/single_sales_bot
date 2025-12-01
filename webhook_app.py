# webhook_app.py
"""
WSGI application for PythonAnywhere or other WSGI servers.
This file simply imports and exposes the Flask application from main.py
"""

import sys
import traceback
import json
import os
from datetime import datetime
from pathlib import Path

# #region agent log
def _debug_log(location, message, data=None, hypothesis_id=None):
    try:
        # Use relative path that works on both local and PythonAnywhere
        script_dir = Path(__file__).parent.absolute()
        log_dir = script_dir / ".cursor"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / "debug.log"
        
        log_entry = {
            "timestamp": int(datetime.now().timestamp() * 1000),
            "location": location,
            "message": message,
            "sessionId": "debug-session",
            "runId": "run1"
        }
        if data is not None:
            log_entry["data"] = data
        if hypothesis_id:
            log_entry["hypothesisId"] = hypothesis_id
        with open(log_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        # Silently fail - don't crash the app if logging fails
        print(f"[debug_log] Failed to write log: {e}")
        pass
# #endregion agent log

try:
    _debug_log("webhook_app.py:11", "Starting import of main module", None, "A")
    from main import application
    _debug_log("webhook_app.py:12", "Successfully imported application from main.py", {"app_type": str(type(application))}, "A")
    print("✅ Successfully imported application from main.py")
except Exception as e:
    try:
        _debug_log("webhook_app.py:14", "ERROR importing application from main.py", {"error": str(e), "error_type": type(e).__name__}, "A")
    except:
        pass  # Don't fail if logging fails
    print(f"❌ ERROR importing application from main.py: {e}")
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
