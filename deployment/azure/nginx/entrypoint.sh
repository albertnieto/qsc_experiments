#!/bin/sh
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

set -e

if [ -z "$ROLE" ]; then
    echo "Error: ROLE environment variable is not set."
    echo "Usage: ROLE=orchestrator|worker1|worker2"
    exit 1
fi

echo "Configuring Nginx for role: $ROLE"
# Debug: List files to confirm location (redirect to stderr to ensure visibility)
ls -R /etc/nginx/custom_configs >&2
ls -R /opt/nginx/conf >&2

# Ensure destination directory exists
mkdir -p /opt/nginx/conf

if [ "$ROLE" = "orchestrator" ]; then
    if [ -f "/etc/nginx/custom_configs/orchestrator.conf" ]; then
        cp /etc/nginx/custom_configs/orchestrator.conf /opt/nginx/conf/nginx.conf
    else
        echo "ERROR: orchestrator.conf not found!" >&2
        exit 1
    fi
elif [ "$ROLE" = "worker1" ]; then
    if [ -f "/etc/nginx/custom_configs/worker1.conf" ]; then
        cp /etc/nginx/custom_configs/worker1.conf /opt/nginx/conf/nginx.conf
    else
        echo "ERROR: worker1.conf not found!" >&2
        exit 1
    fi
elif [ "$ROLE" = "worker2" ]; then
    if [ -f "/etc/nginx/custom_configs/worker2.conf" ]; then
        cp /etc/nginx/custom_configs/worker2.conf /opt/nginx/conf/nginx.conf
    else
        echo "ERROR: worker2.conf not found!" >&2
        exit 1
    fi
else
    echo "Unknown ROLE: $ROLE" >&2
    exit 1
fi

# Debug mode to keep container alive for inspection
if [ "$DEBUG_SLEEP" = "true" ]; then
    echo "DEBUG_SLEEP is true. Sleeping indefinitely..."
    tail -f /dev/null
fi

echo "Starting Nginx..."
exec nginx -g "daemon off;"
