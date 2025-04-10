# Use an official Python runtime as a parent image
# Using slim-bullseye often results in smaller images
FROM python:3.10-slim-bullseye

# Set environment variables
# Prevents python creating .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Prevents python buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that OR-Tools might need (if any - often handled by pip package)
# RUN apt-get update && apt-get install -y --no-install-recommends some-dependency && rm -rf /var/lib/apt/lists/*
# ^-- Uncomment and add dependencies if needed based on OR-Tools docs or runtime errors

# Install Python dependencies
# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Define the port the app will run on (Cloud Run expects 8080 by default)
ENV PORT=8080
EXPOSE 8080

# Command to run the application using uvicorn
# Make sure 'main:app' matches your filename and FastAPI app variable name
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"] 