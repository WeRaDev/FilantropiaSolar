# FilantropiaSolar ML Microservice
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create models directory
RUN mkdir -p /app/models

# Environment
ENV PYTHONUNBUFFERED=1
ENV MODEL_PATH=/app/models

# Expose port
EXPOSE 8501

# Health check (using Python since curl not available in slim image)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/health')" || exit 1

# Run server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8501"]
