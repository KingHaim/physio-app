#!/bin/bash

# Load API key from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    echo "Loaded environment variables from .env file"
elif [ -f .env.new ]; then
    export $(grep -v '^#' .env.new | xargs)
    echo "Loaded environment variables from .env.new file"
else
    echo "No .env file found. API integration may not work."
fi

# Make sure Python-dotenv is installed
python -m pip install python-dotenv

# Stop any running Flask processes
echo "Stopping any running Flask servers..."
pkill -f flask || true

# Run test script to validate API key and find working endpoint
echo "Testing DeepSeek API connection..."
./test_deepseek_api.py

# Check if working_endpoint.txt exists
if [ -f working_endpoint.txt ]; then
    export DEEPSEEK_API_ENDPOINT=$(cat working_endpoint.txt)
    echo "Using DeepSeek API endpoint: $DEEPSEEK_API_ENDPOINT"
fi

echo "Starting Flask server with API key..."
export FLASK_APP=run.py
flask run 