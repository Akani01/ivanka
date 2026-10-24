FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps (needed for Pillow, psycopg, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

# 1. Install Python deps first (cache-friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Copy source
COPY . .

# 3. Create non-root user
RUN useradd -m ivanka

# 4. Collect static AS ROOT (so it can write everywhere)
#    Then hand ownership of /app to ivanka before switching user
RUN mkdir -p /app/media /app/staticfiles \
 && python manage.py collectstatic --noinput \
 && chown -R ivanka:ivanka /app

# 5. Drop privileges
USER ivanka

EXPOSE 8000

CMD ["python", "-m", "gunicorn", "ivanka.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]