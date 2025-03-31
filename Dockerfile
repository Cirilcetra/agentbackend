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

# Expose port (will use the PORT env var at runtime)
EXPOSE 8000

# Use the entrypoint script to properly handle PORT env var
ENTRYPOINT ["/app/entrypoint.sh"] 