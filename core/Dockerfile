# LocalTopSH Core - Python ReAct Agent
FROM python:3.11-bookworm

# Install tools for agent and users
RUN apt-get update && apt-get install -y \
    git curl wget gawk \
    build-essential cmake \
    jq htop tree ripgrep fd-find \
    zip unzip tar \
    iproute2 net-tools lsof \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/fdfind /usr/bin/fd

# Pre-install common Python packages
RUN pip install --no-cache-dir flask fastapi uvicorn requests

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy all Python modules
COPY *.py ./
COPY tools/ ./tools/
COPY tests/ ./tests/

# Copy config files from src/
COPY src/agent/system.txt ./src/agent/
COPY src/approvals/blocked-patterns.json ./src/approvals/

# Copy entrypoint script (strip CRLF so it runs on Linux regardless of host)
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Create workspace and Google credentials directory
RUN mkdir -p /workspace && chmod 777 /workspace && \
    mkdir -p /data/google_creds && chmod 777 /data/google_creds

ENV AGENT_CWD=/workspace

ENTRYPOINT ["/entrypoint.sh"]
