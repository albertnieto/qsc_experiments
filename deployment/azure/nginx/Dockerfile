# Pinned to the Docker Hub `latest` index digest as of 2026-08-17
# (tag `latest` itself is a moving pointer).
FROM openquantumsafe/nginx@sha256:4fe9d9c284ecfa561d668ea312ac5c448894fec532e5e5e4bfd7b4d823947d2e

USER root


# Install basic tools if needed (alpine based usually)
# RUN apk add --no-cache bash

# Create directory for custom configs
RUN mkdir -p /etc/nginx/custom_configs

# Copy configurations
COPY deployment/azure/nginx/orchestrator.conf /etc/nginx/custom_configs/
COPY deployment/azure/nginx/worker1.conf /etc/nginx/custom_configs/
COPY deployment/azure/nginx/worker2.conf /etc/nginx/custom_configs/

# Copy certificates
COPY certs/ /etc/nginx/certs/

# Copy entrypoint
COPY deployment/azure/nginx/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
