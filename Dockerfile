# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install uv, the package manager
RUN pip install uv

# Copy the dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv pip sync --system pyproject.toml

# Copy the rest of the application code
COPY . .

# Expose the ports the app runs on
EXPOSE 2080
EXPOSE 2081

# Define the command to run the app
CMD ["uv", "run", "python", "app/main.py"]
