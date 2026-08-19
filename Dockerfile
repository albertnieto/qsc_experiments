FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies for liboqs
RUN apt-get update && apt-get install -y \
    cmake \
    gcc \
    git \
    libssl-dev \
    make \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Build and install a pinned liboqs release.
ARG LIBOQS_REF=0.14.0
ARG LIBOQS_PYTHON_REF=v0.14
RUN git clone --depth=1 --branch ${LIBOQS_REF} https://github.com/open-quantum-safe/liboqs && \
    cmake -S liboqs -B liboqs/build -DBUILD_SHARED_LIBS=ON && \
    cmake --build liboqs/build --parallel 8 && \
    cmake --build liboqs/build --target install && \
    rm -rf liboqs

ENV LD_LIBRARY_PATH=/usr/local/lib

# Install the matching pinned liboqs-python release.
RUN git clone --depth=1 --branch ${LIBOQS_PYTHON_REF} https://github.com/open-quantum-safe/liboqs-python && \
    cd liboqs-python && \
    pip install --no-cache-dir . && \
    cd .. && \
    rm -rf liboqs-python

WORKDIR /app

# Copy project files. Certificates are generated on the host and mounted
# at runtime (see deployment/docker-compose.yml); they are not in git.
COPY requirements.txt ./
COPY src/ ./src/
COPY tests/ ./tests/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Verify liboqs-python
RUN python -c "import oqs; print('liboqs-python installed'); print('Algorithms:', oqs.get_enabled_sig_mechanisms()[:5])"

CMD ["python", "-m", "src.pqc_agents.orchestrator_server"]
