# Use the official Python image as a parent image.
# Using a specific version like 3.9-slim is good practice for reproducibility.
FROM python:3.9-slim

# Set the working directory in the container.
# This is where your code will live.
WORKDIR /app

# Set environment variables for the port Gunicorn will listen on.
# Cloud Run automatically sets the PORT environment variable,
# so we will use it in our command.
# ENV PORT 8080 # This line is often not needed as Cloud Run provides it.

# Copy the requirements file into the container first.
# This allows Docker to cache the layer and reuse it if requirements.txt hasn't changed.
COPY requirements.txt .

# Install dependencies from requirements.txt.
# Ensure gunicorn is listed in this file.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container.
# This includes app.py, templates, and any static files.
COPY . .

# The command to run the application using Gunicorn.
# The `--bind` part is crucial for Cloud Run. It tells Gunicorn to listen on
# all network interfaces at the port specified by the PORT environment variable.
# 'app:app' means 'run the callable object named "app" from the file named "app.py"'.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app