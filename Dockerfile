# Use the official Python image as a parent image.
# Using a specific version like 3.9-slim is good practice for reproducibility.
FROM python:3.9-slim

# Set the working directory in the container.
# This is where your code will live.
WORKDIR /app

# Set environment variables for Gunicorn, which is used to run the app.
ENV PORT 8080

# Copy the requirements file into the container first.
# This allows Docker to cache the layer and reuse it if requirements.txt hasn't changed.
COPY requirements.txt .

# Install dependencies from requirements.txt.
# We've added gunicorn here.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container.
# This includes app.py, templates, and any static files.
COPY . .

# Expose the port that the container listens on.
EXPOSE 8080

# The command to run the application using Gunicorn.
# The `--bind 0.0.0.0:$PORT` part is crucial for Cloud Run/Container environments.
# It tells Gunicorn to listen on all network interfaces at the port specified by the PORT environment variable.
CMD ["python", "app.py"]
