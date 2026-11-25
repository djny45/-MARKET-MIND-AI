# Pinned by full version + Alpine release, not just major.minor, so the build is
# reproducible and Trivy's DS-0001 ("specify a tag") stays satisfied.
FROM python:3.12.16-alpine3.24 AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt ./requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip==26.2.0 \
    && /opt/venv/bin/pip install -r requirements.txt \
    && /opt/venv/bin/pip install --upgrade \
        certifi==2026.10.18 msgpack==1.2.3 urllib3==2.8.0

# The runtime needs an interpreter, not an installer. Removing pip/setuptools
# eliminates the vendored copies reported as certifi/msgpack/urllib3/setuptools
# findings. Verified app.main imports and serves /api/ready without them.
RUN rm -rf /opt/venv/lib/python*/site-packages/pip \
           /opt/venv/lib/python*/site-packages/pip-*.dist-info \
           /opt/venv/lib/python*/site-packages/setuptools \
           /opt/venv/lib/python*/site-packages/setuptools-*.dist-info \
           /opt/venv/lib/python*/site-packages/pkg_resources \
           /opt/venv/lib/python*/site-packages/_distutils_hack \
           /opt/venv/lib/python*/site-packages/distutils-precedence.pth \
    && find /opt/venv -name '__pycache__' -type d -prune -exec rm -rf {} +


FROM python:3.12.16-alpine3.24 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MARKET_MIND_DB=/data/market_mind.db \
    PATH="/opt/venv/bin:$PATH"

# Upgrade the Alpine packages pinned in the base tag (libcrypto3/libssl3/zlib
# had fixes available in 3.5.9-r1/1.4-r0 at scan time). The container scan
# remains fail-closed for anything Alpine has not fixed.
#
# The runtime installs nothing, so remove the base image's system pip as well.
# Leaving pip 25.0.1 in /usr/local/lib/python3.12 reintroduced five MEDIUM CVEs
# (CVE-2025-8869, CVE-2026-13346, CVE-2026-3219, CVE-2026-6357, CVE-2026-8643).
RUN apk upgrade --no-cache \
    && rm -rf /usr/local/lib/python3.12/site-packages/pip \
              /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
              /usr/local/lib/python3.12/site-packages/setuptools \
              /usr/local/lib/python3.12/site-packages/setuptools-*.dist-info \
              /usr/local/lib/python3.12/site-packages/pkg_resources \
              /usr/local/lib/python3.12/site-packages/_distutils_hack \
              /usr/local/lib/python3.12/site-packages/distutils-precedence.pth \
    && addgroup -g 10001 -S appuser \
    && adduser -u 10001 -S -G appuser -h /home/appuser appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY backup_database.py restore_database.py ./

USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
