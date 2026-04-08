# ── Base: Python 3.11 slim ────────────────────────────────────────────────────
FROM python:3.11-slim

# Install Node.js 20 + build tools (needed to compile the TS environment)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        ca-certificates \
        build-essential \
        git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g typescript \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps ───────────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy project ──────────────────────────────────────────────────────────────
COPY . /app

# ── Pre-install Node deps for the TypeScript workspace ────────────────────────
# (agents may run `npm run build`; deps must already be present)
RUN cd /app/environment && npm ci --no-audit --no-fund

# ── Environment ───────────────────────────────────────────────────────────────
ENV MONACO_WORKSPACE=/app/environment
ENV PORT=7860
# HF_TOKEN, API_BASE_URL, MODEL_NAME injected at runtime

# HuggingFace Spaces routes port 7860
EXPOSE 7860

# ── Start FastAPI server ──────────────────────────────────────────────────────
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860"]
