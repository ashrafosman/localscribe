#!/bin/bash

# LocalScribe Startup Script

echo "Starting LocalScribe..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Check if .env file exists, if not copy from example
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit .env file with your configuration"
fi

# Function to open browser
open_browser() {
    local url="$1"
    echo "Opening browser to $url..."
    
    # Detect OS and open browser accordingly
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        open "$url"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v xdg-open > /dev/null; then
            xdg-open "$url"
        elif command -v gnome-open > /dev/null; then
            gnome-open "$url"
        else
            echo "Please open your browser and navigate to $url"
        fi
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        # Windows
        start "$url"
    else
        echo "Please open your browser and navigate to $url"
    fi
}

# Start the Flask application in background and capture PID
echo "Starting LocalScribe application..."
./venv/bin/python app.py &
APP_PID=$!

# Wait a moment for the server to start
sleep 3

# Get the port from environment or use default
PORT=${PORT:-5001}
URL="http://localhost:$PORT"

# Check if server is running by making a simple request
if curl -s "$URL" > /dev/null 2>&1; then
    open_browser "$URL"
else
    echo "Server may still be starting up. Please open your browser and navigate to $URL"
fi

# Wait for the Flask application to finish
wait $APP_PID
