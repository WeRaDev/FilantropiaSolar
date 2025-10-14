# ===========================================
# FilantropiaSolar - Multi-stage Dockerfile
# ===========================================

# ============================================
# Base image with Python 3.11
# ============================================
# Global build arg for selecting final stage (ensures availability during parse)
ARG BUILD_TARGET=production
FROM python:3.11-slim as base

# Metadata
LABEL org.opencontainers.image.title="FilantropiaSolar"
LABEL org.opencontainers.image.description="Advanced Solar Energy Analysis Application"
LABEL org.opencontainers.image.vendor="FilantropiaSolar Team"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.url="https://github.com/your-org/filantropia-solar"
LABEL org.opencontainers.image.documentation="https://filantropia-solar.readthedocs.io"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Create non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash appuser

# System dependencies and cleanup
RUN apt-get update && apt-get install -y \
    # Build dependencies
    gcc \
    g++ \
    libc6-dev \
    # Scientific computing dependencies
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    # System utilities
    curl \
    wget \
    ca-certificates \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ============================================
# Development stage
# ============================================
FROM base as development

# Install development dependencies
RUN apt-get update && apt-get install -y \
    git \
    vim \
    htop \
    tree \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements-dev.txt && \
    pip cache purge

# Copy source code
COPY . .

# Install package in development mode
RUN pip install -e .

# Switch to non-root user
USER appuser

# Development command
CMD ["python", "main.py"]

# ============================================
# Production build stage
# ============================================
FROM base as builder

WORKDIR /app

# Install build dependencies
RUN pip install --upgrade pip build wheel

# Copy source code and build files
COPY pyproject.toml README.md LICENSE ./
COPY main.py ./
COPY src/ src/

# Build the package
RUN python -m build --wheel

# ============================================
# Production runtime stage
# ============================================
FROM base as production

# Install production system dependencies
RUN apt-get update && apt-get install -y \
    # Minimal runtime dependencies
    libgcc-s1 \
    libgomp1 \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

# Copy and install the built wheel from builder stage
COPY --from=builder /app/dist/*.whl /tmp/
COPY requirements.txt ./

# Install the application
RUN pip install --upgrade pip && \
    pip install --no-deps /tmp/*.whl && \
    pip install -r requirements.txt && \
    pip cache purge && \
    rm -rf /tmp/*.whl

# Create directories for data and models
RUN mkdir -p /app/data /app/models /app/logs /app/exports && \
    chown -R appuser:appuser /app

# Copy configuration files and main application
COPY --chown=appuser:appuser config/ config/
COPY --chown=appuser:appuser main.py ./

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app'); import src.data_processing; print('OK')" || exit 1

# Default command
CMD ["python", "main.py"]

# ============================================
# API service stage
# ============================================
FROM production as api

# Install API dependencies
USER root
RUN pip install fastapi uvicorn[standard] python-multipart websockets && \
    pip cache purge

USER appuser

# Expose API port
EXPOSE 8000

# API health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# API command
CMD ["uvicorn", "filantropia_solar.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============================================
# GPU-enabled stage (optional)
# ============================================
FROM nvidia/cuda:12.1-runtime-ubuntu22.04 as gpu

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set Python alias
RUN ln -s /usr/bin/python3.11 /usr/bin/python

WORKDIR /app

# Copy from production stage
COPY --from=production /app /app

# Install GPU-specific ML libraries
RUN pip install cuml-cu12 cudf-cu12 --extra-index-url https://pypi.anaconda.org/rapidsai-wheels-nightly/simple

USER appuser

CMD ["python", "main.py"]

# ============================================
# Final stage selection (fixed to production for CI builds)
# ============================================
FROM production as final
