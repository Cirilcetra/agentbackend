FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Make start script executable
RUN chmod +x /app/start.sh

# Expose port
EXPOSE 8000

# Use shell form to ensure environment variable expansion
CMD /app/start.sh 