# syntax=docker/dockerfile:1

# Backend image for Q-AEGIS Shield.
#
# Two stages so build-time pip machinery and caches do not ship in the runtime
# image. Python 3.13 matches the version pinned in CI; keep the two in step, a
# mismatch means the image runs an interpreter no test ever exercised.

# --------------------------------------------------------------------------
# Stage 1: build dependencies into a self-contained virtualenv, and compile
# the native liboqs shared library that the post-quantum crypto depends on.
# --------------------------------------------------------------------------
FROM python:3.13-slim AS builder

WORKDIR /build

# liboqs-python (see requirements.txt) is only a thin ctypes wrapper: on import
# it loads a NATIVE liboqs shared object, and if it cannot find one it tries to
# git-clone and CMake-build liboqs *at runtime*. The slim runtime image has no
# compiler, so that runtime build fails and hybrid/PQ encryption then fails
# closed. We therefore build liboqs here, at image-build time, and ship the
# resulting .so — the runtime never compiles anything.
#
# Keep LIBOQS_VERSION in step with the liboqs-python pin in requirements.txt:
# liboqs-python resolves the native version from its own package version, so a
# mismatch would mean the wrapper and the library disagree on the ABI.
ARG LIBOQS_VERSION=0.16.0
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git cmake ninja-build gcc libc6-dev libssl-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && git config --global http.version HTTP/1.1 \
    && for attempt in 1 2 3 4 5; do \
         echo "liboqs clone attempt ${attempt}" \
         && git clone --depth 1 --branch "${LIBOQS_VERSION}" \
              https://github.com/open-quantum-safe/liboqs /tmp/liboqs \
         && break; \
         rm -rf /tmp/liboqs; sleep 5; \
       done \
    && test -d /tmp/liboqs/.git \
    && cmake -S /tmp/liboqs -B /tmp/liboqs/build -GNinja \
        -DBUILD_SHARED_LIBS=ON \
        -DOQS_BUILD_ONLY_LIB=ON \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/opt/liboqs \
    && cmake --build /tmp/liboqs/build --parallel \
    && cmake --install /tmp/liboqs/build \
    && rm -rf /tmp/liboqs

# Copied on its own, before the application code, so this layer is reused as
# long as dependencies are unchanged. Copying the source first would reinstall
# every dependency on any code edit.
COPY requirements.txt ./

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Prove the native library loads under the wrapper during the build, so a
# broken liboqs build fails the image here rather than at first PQ request.
# ML-KEM-1024 and ML-DSA-87 are the algorithms the crypto engine requires.
ENV OQS_INSTALL_PATH=/opt/liboqs
RUN /opt/venv/bin/python -c "import oqs; kem=oqs.get_enabled_kem_mechanisms(); sig=oqs.get_enabled_sig_mechanisms(); assert 'ML-KEM-1024' in kem, 'ML-KEM-1024 missing'; assert 'ML-KEM-768' in kem, 'ML-KEM-768 missing'; assert 'ML-DSA-87' in sig, 'ML-DSA-87 missing'; print('liboqs OK: ML-KEM + ML-DSA enabled')"

# --------------------------------------------------------------------------
# Stage 2: runtime.
# --------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

# OQS_INSTALL_PATH tells liboqs-python where the prebuilt native library lives
# (it loads $OQS_INSTALL_PATH/lib/liboqs.so), so the wrapper never attempts a
# runtime compile. LD_LIBRARY_PATH lets liboqs' own transitive deps resolve.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    OQS_INSTALL_PATH=/opt/liboqs \
    LD_LIBRARY_PATH=/opt/liboqs/lib

# Run as an unprivileged user. A container process does not need root, and
# defaulting to it turns a container escape into a host-root problem.
RUN groupadd --system --gid 1001 qaegis \
    && useradd --system --uid 1001 --gid qaegis --no-create-home qaegis

COPY --from=builder /opt/venv /opt/venv
# The compiled post-quantum library. Without this the PQ/hybrid profiles fail
# closed at runtime (LiboqsUnavailableError); AES-256 would still work.
COPY --from=builder /opt/liboqs /opt/liboqs

WORKDIR /srv
COPY --chown=qaegis:qaegis app ./app

# The trained sensitivity classifier (FR-1, SPEC.md 3.2). Baked like liboqs and
# the embedding model so the image is self-contained and the runtime never
# fetches it. Ships the multi-genre hashing-SVM bundle (its evaluation report
# rides along for provenance) — trained across diplomatic cables, code, prose,
# forms, medical/financial and synthetic detector-positive documents so it
# generalises beyond any single genre. CLASSIFIER_MODEL_PATH below activates the
# trained engine (paired with the deterministic detector backstop in
# app/classifier/detectors.py); clear it to fall back to the keyword engine.
COPY --chown=qaegis:qaegis \
     artifacts/classifier/multigenre-hashing-svm-1.0.0.joblib \
     artifacts/classifier/multigenre-hashing-svm-1.0.0.evaluation.json \
     ./artifacts/classifier/
ENV CLASSIFIER_MODEL_PATH=/srv/artifacts/classifier/multigenre-hashing-svm-1.0.0.joblib

# Uploaded document bytes live here (DOCUMENT_STORAGE_DIR). Create and hand the
# tree to the unprivileged user BEFORE dropping privileges, so writes under the
# mounted volume succeed. The compose volume must be fresh (or chowned) to
# inherit this ownership; a pre-existing root-owned volume masks it.
RUN mkdir -p /data/documents && chown -R qaegis:qaegis /data

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
