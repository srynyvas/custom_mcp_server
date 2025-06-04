FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy FastAPI requirements
COPY fastapi_requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r fastapi_requirements.txt

# Copy FastAPI application
COPY fastapi_service.py .

# Create non-root user
RUN groupadd -r apiuser && useradd -r -g apiuser apiuser
RUN chown -R apiuser:apiuser /app
USER apiuser

# Expose port
EXPOSE 8000

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI application
CMD ["python", "-m", "uvicorn", "fastapi_service:app", "--host", "0.0.0.0", "--port", "8000"]
