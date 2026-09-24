# Beyond2U AI-Powered IT Helpdesk — Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for SQLite database, instance, and ML models
RUN mkdir -p instance app/ml/models

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_APP=wsgi.py \
    FLASK_CONFIG=production \
    PORT=5000

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--access-logfile", "-", "wsgi:app"]
