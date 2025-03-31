FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Expose port (will use fixed port 8000)
EXPOSE 8000

# Debug - show contents of entrypoint script
RUN cat /app/entrypoint.sh

# Use the entrypoint script
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"] 