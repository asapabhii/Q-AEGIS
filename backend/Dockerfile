# syntax=docker/dockerfile:1

# Backend image for Q-AEGIS Shield.
#
# Two stages so build-time pip machinery and caches do not ship in the runtime
# image. Python 3.13 matches the version pinned in CI; keep the two in step, a
# mismatch means the image runs an interpreter no test ever exercised.

# --------------------------------------------------------------------------
# Stage 1: build dependencies into a self-contained virtualenv.
# --------------------------------------------------------------------------
FROM python:3.13-slim AS builder

WORKDIR /build

# Install build tools for liboqs (post-quantum cryptography) and BLAS for qiskit-aer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    git \
    libssl-dev \
    libopenblas-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Build and install liboqs C library
RUN git clone --branch 0.16.0 --depth 1 https://github.com/open-quantum-safe/liboqs.git \
    && cd liboqs \
    && mkdir build && cd build \
    && cmake -GNinja -DCMAKE_INSTALL_PREFIX=/opt/liboqs -DBUILD_SHARED_LIBS=ON -DOQS_USE_OPENSSL=ON .. \
    && ninja install

# Copied on its own, before the application code, so this layer is reused as
# long as dependencies are unchanged. Copying the source first would reinstall
# every dependency on any code edit.
COPY requirements.txt ./

# Set environment variables for liboqs so liboqs-python finds it
ENV LD_LIBRARY_PATH="/opt/liboqs/lib:/opt/liboqs/lib64" \
    C_INCLUDE_PATH="/opt/liboqs/include"

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# --------------------------------------------------------------------------
# Stage 2: runtime.
# --------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

# Install libssl (OpenSSL) required by liboqs at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    LD_LIBRARY_PATH="/opt/liboqs/lib:/opt/liboqs/lib64"

# Run as an unprivileged user. A container process does not need root, and
# defaulting to it turns a container escape into a host-root problem.
RUN groupadd --system --gid 1001 qaegis \
    && useradd --system --uid 1001 --gid qaegis --no-create-home qaegis

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/liboqs /opt/liboqs

# Configure dynamic linker so python ctypes (via liboqs-python) can find liboqs.so
RUN echo "/opt/liboqs/lib" > /etc/ld.so.conf.d/liboqs.conf \
    && echo "/opt/liboqs/lib64" >> /etc/ld.so.conf.d/liboqs.conf \
    && ldconfig

WORKDIR /srv
COPY --chown=qaegis:qaegis app ./app

USER qaegis

EXPOSE 8000

# Uses the standard library rather than curl, which is absent from the slim
# base image and not worth installing for one probe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"]

# No --reload, and a single worker. Process management and TLS termination are
# the deployment layer's job. TLS is NOT configured here, see AGENTS.md's
# in-transit requirement and the outstanding note in infra/docker-compose.yml;
# do not read this file's silence as that requirement being satisfied.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
