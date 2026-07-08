FROM python:3.12.3

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --retries 5 -r requirements.txt

COPY . /app/

COPY entrypoint.sh /app/entrypoint.sh

RUN useradd -m -u 1000 appuser && \
    chmod +x /app/entrypoint.sh && \
    mkdir -p /app/staticfiles && \
    chmod 755 /app/staticfiles && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]
