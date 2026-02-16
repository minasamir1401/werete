#!/bin/bash
set -e

echo "==========================================="
echo "   Setting up Backend for Linux VPS"
echo "==========================================="

# Update package list and install Python dependencies if needed
echo "[1/4] Checking system dependencies..."
if ! command -v python3 &> /dev/null
then
    echo "Python3 not found. Installing..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
else
    echo "Python3 is installed."
fi

# Create virtual environment
echo "[2/4] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

# Activate venv and install requirements
echo "[3/4] Installing Python requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo "[4/4] Setting up directories..."
mkdir -p logs
touch logs/backend-error.log
touch logs/backend-out.log

echo ""
echo "==========================================="
echo "   Setup Complete! Backend is ready."
echo "==========================================="
echo "To run the server manually:"
echo "source venv/bin/activate"
echo "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
