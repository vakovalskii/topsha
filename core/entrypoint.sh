#!/bin/bash
# Entrypoint for core container
# Ensures workspace directory has correct permissions

set -e

echo "🔧 Initializing workspace permissions..."

# Ensure workspace directories exist with correct permissions
mkdir -p /workspace/_shared
chmod 777 /workspace 2>/dev/null || true
chmod 777 /workspace/_shared 2>/dev/null || true

# Ensure _shared files are writable
if [ -f /workspace/_shared/admin_config.json ]; then
    chmod 666 /workspace/_shared/admin_config.json 2>/dev/null || true
fi

echo "✅ Workspace ready"

# Start the application
exec python -u main.py
