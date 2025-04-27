FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Log the PORT environment variable
RUN echo "Assigned PORT inside container build: $PORT"

# Expose port (doesn't actually publish it, just metadata)
# EXPOSE 8000 
# Railway uses the PORT env var, so EXPOSE might be irrelevant or potentially confusing

# Command to run the application, ensuring $PORT is evaluated by a shell
# CMD ["/bin/sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
CMD ["/bin/sh", "-c", "echo \"Attempting to start Uvicorn on PORT: [$PORT]\" && uvicorn app.main:app --host 0.0.0.0 --port $PORT"] 