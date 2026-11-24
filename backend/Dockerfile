FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MARKET_MIND_DB=/data/market_mind.db

WORKDIR /app
COPY requirements.txt ./requirements.txt
# Refresh OS packages so the image picks up security fixes published after the
# base tag was cut. The container scan remains fail-closed for anything Debian
# has not fixed yet.
RUN apt-get update \
    && apt-get -y --no-install-recommends upgrade \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade pip==26.2.0 \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade \
        certifi==2026.10.18 msgpack==1.2.3 setuptools==83.0.0 urllib3==2.8.0 \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data

COPY app ./app
COPY backup_database.py restore_database.py ./
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
