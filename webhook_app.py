# webhook_app.py
"""
WSGI application for PythonAnywhere or other WSGI servers.
This file simply imports and exposes the Flask application from main.py
"""

import sys
import traceback
import json
from datetime import datetime

# #region agent log
def _debug_log(location, message, data=None, hypothesis_id=None):
    try:
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
        with open("/Users/g.dvoryak/Desktop/single_sales_bot/.cursor/debug.log", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except:
        pass
# #endregion agent log

try:
    _debug_log("webhook_app.py:11", "Starting import of main module", None, "A")
    from main import application
    _debug_log("webhook_app.py:12", "Successfully imported application from main.py", {"app_type": str(type(application))}, "A")
    print("✅ Successfully imported application from main.py")
except Exception as e:
    _debug_log("webhook_app.py:14", "ERROR importing application from main.py", {"error": str(e), "error_type": type(e).__name__}, "A")
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
