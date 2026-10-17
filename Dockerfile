# Shop image for one Windows PC.
# Stage 1 builds the React app. Stage 2 runs Django with Waitress.
# The database, photos, and backups stay in the shop-data volume, not in the image.

FROM node:22-bookworm-slim AS ui
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm

# Production mode: debug off, per-install secret stored under /data.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MM_PACKAGED=1 \
    MM_DEBUG=0 \
    MM_DATA_DIR=/data \
    MM_FRONTEND_DIST=/opt/shop/frontend_dist

WORKDIR /opt/shop

COPY backend/requirements-runtime.txt /tmp/requirements-runtime.txt
RUN pip install --no-cache-dir -r /tmp/requirements-runtime.txt \
    && useradd --create-home --uid 1000 --shell /usr/sbin/nologin shop \
    && mkdir -p /data \
    && chown shop:shop /data

COPY backend/ /opt/shop/
COPY --from=ui /src/frontend/dist /opt/shop/frontend_dist

EXPOSE 8000
VOLUME /data

# The launcher migrates before it listens, so allow a slow first start.
HEALTHCHECK --interval=5s --timeout=3s --start-period=40s --retries=24 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/', timeout=2)"

CMD ["python", "packaging/docker_entry.py"]
