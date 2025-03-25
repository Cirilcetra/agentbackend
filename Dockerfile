FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy environment files first (these are used by start.py)
COPY .env* .
COPY .railway.secrets.json .

# Copy the rest of the code
COPY . .

# Make sure environment files have the right permissions
RUN chmod 644 .env* .railway.secrets.json

# Make start.py executable
RUN chmod +x start.py

# Default port for the application (can be overridden by Railway)
ENV PORT=8000
ENV RAILWAY_ENVIRONMENT=true

# NOTE: Add your environment variables through the Railway dashboard
# DO NOT hardcode sensitive values in this file
# Required variables:
# - OPENAI_API_KEY
# - SUPABASE_URL
# - SUPABASE_KEY
# - DATABASE_URL

# Expose the port
EXPOSE 8000

# Command to run the application
CMD ["python", "start.py"] 