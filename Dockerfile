FROM python:3.13-slim

WORKDIR /app

# Install system deps for psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy application code
COPY src/ src/
COPY langgraph.json .

# Default command (overridden by docker-compose)
CMD ["langgraph", "dev", "--no-browser", "--host", "0.0.0.0"]
