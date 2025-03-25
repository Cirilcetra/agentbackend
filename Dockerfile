FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Default port for the application (can be overridden by Railway)
ENV PORT=8000

# Expose the port
EXPOSE ${PORT}

# Command to run the application
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} 