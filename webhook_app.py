# webhook_app.py
"""
WSGI application for PythonAnywhere or other WSGI servers.
This file simply imports and exposes the Flask application from main.py
"""

from main import application

# This is the WSGI application that PythonAnywhere will use
# In PythonAnywhere Web tab, set:
# - Source code: /home/yourusername/single_sales_bot
# - WSGI configuration file should import: from webhook_app import application
