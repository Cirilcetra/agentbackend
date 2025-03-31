FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose port
EXPOSE ${PORT}

# Command to run the application with debug logging
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --log-level debug 