#!/bin/bash

# Deployment script for Todo App Backend

echo "Starting deployment for Todo App Backend..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Initialize database
echo "Initializing database..."
python init_db.py

# Start the application
echo "Starting the application..."
python app.py

# Deactivate virtual environment when done
deactivate