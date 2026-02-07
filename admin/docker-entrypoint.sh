#!/bin/sh
set -e

# Read admin credentials
# User from env, password from Docker secret or env
ADMIN_USER="${ADMIN_USER:-admin}"

# Try to read password from Docker secret first
if [ -f "$ADMIN_PASSWORD_FILE" ]; then
    ADMIN_PASSWORD=$(cat "$ADMIN_PASSWORD_FILE" | tr -d '\n')
elif [ -n "$ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD="$ADMIN_PASSWORD"
else
    ADMIN_PASSWORD="admin"
    echo "WARNING: Using default password 'admin'. Change it in secrets/admin_password.txt!"
fi

# Create htpasswd file
htpasswd -bc /etc/nginx/.htpasswd "$ADMIN_USER" "$ADMIN_PASSWORD"

echo "✓ Admin panel auth configured for user: $ADMIN_USER"

# Execute the main command
exec "$@"
