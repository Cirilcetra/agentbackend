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

# Create a startup script
RUN echo '#!/bin/bash\n\
echo "Starting AI Agent Backend"\n\
echo "PORT: $PORT"\n\
echo "HOST: 0.0.0.0"\n\
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1\n\
' > /app/start.sh && chmod +x /app/start.sh

# Copy the rest of the code
COPY . .

# Default port for the application (can be overridden by Railway)
ENV PORT=8000
ENV RAILWAY_ENVIRONMENT=true

# Expose the port
EXPOSE ${PORT}

# Command to run the application
CMD ["/app/start.sh"] 