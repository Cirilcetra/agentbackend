FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application using shell form to allow $PORT expansion
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT 