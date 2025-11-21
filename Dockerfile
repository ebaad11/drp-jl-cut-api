# Use Python 3.11 slim for smaller image size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y \
    zip \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements-api.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy all Python modules
COPY drp_io.py .
COPY resolve_parse.py .
COPY cuts_model.py .
COPY cuts_transform.py .
COPY api.py .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port (Railway will override this)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Start the application
CMD ["python", "api.py"]


