#!/bin/bash

# Development startup script with hot reload

echo "🚀 Starting development environment with hot reload..."

# Option 1: Use development compose file
if [ "$1" = "dev" ]; then
    echo "Using docker-compose.dev.yml..."
    docker-compose -f docker-compose.dev.yml up --build
else
    # Option 2: Use override file (default)
    echo "Using docker-compose.yml with overrides..."
    docker-compose up --build
fi