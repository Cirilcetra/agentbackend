FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Make start script executable
RUN chmod +x /app/start.sh

# Expose port
EXPOSE 8080

# Use shell form to ensure environment variable expansion
CMD ["/bin/bash", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"] 