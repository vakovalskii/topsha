FROM node:22-slim

# Install dependencies for Playwright and Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN npx playwright install-deps chromium
RUN npx playwright install chromium

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Build TypeScript
RUN npm run build

# Create workspace directory
RUN mkdir -p /workspace

# Expose port for health checks (optional)
EXPOSE 3000

# Default command - can be overridden
CMD ["npm", "run", "telegram"]
