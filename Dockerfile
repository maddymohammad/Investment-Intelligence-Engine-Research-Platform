FROM python:3.11-slim

LABEL maintainer="Investment Intelligence Engine"
LABEL description="Research-only stock analysis platform — no trades, no brokerage connections"

# System dependencies for weasyprint + lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create runtime directories
RUN mkdir -p db reports/daily logs

# Default to scheduler mode; override with CMD in docker-compose for other services
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

EXPOSE 8501

CMD ["python", "-m", "src.scheduler"]
