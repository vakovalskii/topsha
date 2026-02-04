# LocalTopSH Gateway Container
FROM node:22-bookworm

# Install tools for agent and users
RUN apt-get update && apt-get install -y \
    git curl wget gawk \
    python3 python3-pip python3-venv \
    build-essential cmake \
    jq htop tree ripgrep fd-find \
    zip unzip tar \
    iproute2 net-tools lsof \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/lib/python*/EXTERNALLY-MANAGED \
    && ln -sf /usr/bin/fdfind /usr/bin/fd

# Pre-install common Python packages
RUN pip install --break-system-packages flask fastapi uvicorn requests

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY tsconfig.json ./
COPY src ./src

# Create workspace with proper permissions
RUN mkdir -p /workspace && chmod 777 /workspace

ENV AGENT_CWD=/workspace

CMD ["npx", "tsx", "src/index.ts"]
