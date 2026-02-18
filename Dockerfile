# ═══════════════════════════════════════════════════════════════
# Nexus Light Orchestrator - Docker Image
# Python + Claude Code CLI + psycopg3
# ═══════════════════════════════════════════════════════════════

FROM python:3.12-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Node.js (for Claude Code CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# App code
WORKDIR /app
COPY orchestrator.py service.py db_layer.py ./
COPY db/ ./db/

# Directories
RUN mkdir -p analyses trades logs skills

# Non-root user (security)
RUN useradd -m nexus && chown -R nexus:nexus /app
USER nexus

# Health check
HEALTHCHECK --interval=60s --timeout=10s \
    CMD python -c "from db_layer import NexusDB; NexusDB().connect().health_check()" || exit 1

ENTRYPOINT ["python"]
CMD ["service.py"]
