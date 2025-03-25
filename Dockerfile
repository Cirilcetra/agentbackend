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

# Create empty env and secrets file to ensure they exist
RUN touch .env.empty
RUN echo '{"_README": "Add environment variables through Railway dashboard"}' > .railway.secrets.json

# Copy environment files first (these are used by start.py)
# Use wildcard patterns that won't fail if files don't exist
COPY .env* ./
# We don't need to copy .railway.secrets.json since we created it above

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