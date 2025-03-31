FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port (will be overridden by Railway's PORT)
EXPOSE 8080

# Run the application using our start script
CMD ["python", "start.py"] 