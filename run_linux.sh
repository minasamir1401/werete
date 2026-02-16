#!/bin/bash
set -e

# Load environment variables (optional if not using .env file directly)
# export $(cat .env | xargs)

# Activate virtual environment
source venv/bin/activate

# Start the server (Using uvicorn)
echo "Starting Backend Server..."
# Run in background (nohup) or use systemd for production
# For now, just run it
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
