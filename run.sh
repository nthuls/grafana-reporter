#!/bin/bash

# Create necessary directories
mkdir -p app/static/uploads
mkdir -p app/static/css
mkdir -p app/static/js
mkdir -p reports

# Set permissions
chmod -R 755 app/static/uploads
chmod -R 755 reports

# Start the application with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
