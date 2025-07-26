# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables to prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install the latest version of uv
RUN pip install --upgrade pip && pip install uv

# Copy only the dependency files first (for better Docker layer caching)
COPY pyproject.toml ./

# Remove any existing virtual environment and lock files completely
RUN rm -rf .venv uv.lock

# Install dependencies using uv with fresh resolution
RUN uv sync --no-dev

# Copy the rest of the application code
COPY . .

# Remove any .venv that might have been copied and recreate fresh
RUN rm -rf .venv && uv sync --no-dev

# Expose the ports the app runs on
EXPOSE 2080
EXPOSE 2081

# Create a start script to run both servers
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Define the command to run both servers
CMD ["/start.sh"]