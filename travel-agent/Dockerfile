# ─────────────────────────────────────────────────────────────────────────────
# Aria Travel Agent — Dockerfile
# Resource Group : Azure_Learning_RZ
# Registry       : ariatravelacr.azurecr.io
#
# Build : docker build -t aria-travel-agent .
# Run   : docker run -p 8000:8000 --env-file .env aria-travel-agent
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Build deps needed by some pip packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first — Docker layer cache skips pip install if unchanged
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Streamlit settings — no config.toml needed
    STREAMLIT_SERVER_PORT=8000 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false \
    STREAMLIT_SERVER_MAX_UPLOAD_SIZE=10

# Non-root user — Azure Container Apps security best practice
RUN groupadd --gid 1000 aria && \
    useradd --uid 1000 --gid aria --shell /bin/bash --create-home aria

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=aria:aria . .

# Azure Container Apps default ingress port
EXPOSE 8000

USER aria

# Health check using Streamlit's built-in health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/_stcore/health')" \
    || exit 1

CMD ["python", "-m", "streamlit", "run", "app.py", \
     "--server.port=8000", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.enableCORS=false", \
     "--server.enableXsrfProtection=false"]
