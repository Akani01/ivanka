FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/media /app/staticfiles && useradd -m ivanka && chown -R ivanka:ivanka /app
USER ivanka
EXPOSE 8000
CMD ["python", "-m", "gunicorn", "ivanka.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
