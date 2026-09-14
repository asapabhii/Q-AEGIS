#!/usr/bin/env bash
# Generate local self-signed TLS material for Q-AEGIS Shield.
# Output: infra/certs/ (gitignored). Never commit these files.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERT_DIR="$ROOT/infra/certs"
mkdir -p "$CERT_DIR"

openssl genrsa -out "$CERT_DIR/ca.key" 4096
cat > "$CERT_DIR/ca.cnf" <<'EOF'
[req]
distinguished_name = dn
x509_extensions = v3_ca
prompt = no

[dn]
CN = Q-AEGIS Local CA
O = Q-AEGIS Dev
C = US

[v3_ca]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
EOF
openssl req -x509 -new -nodes -key "$CERT_DIR/ca.key" -sha256 -days 825 \
  -out "$CERT_DIR/ca.crt" -config "$CERT_DIR/ca.cnf"

cat > "$CERT_DIR/server.ext" <<'EOF'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = postgres
DNS.3 = redis
DNS.4 = backend
DNS.5 = qaegis-postgres
DNS.6 = qaegis-redis
DNS.7 = qaegis-backend
IP.1 = 127.0.0.1
EOF

openssl genrsa -out "$CERT_DIR/server.key" 2048
openssl req -new -key "$CERT_DIR/server.key" -out "$CERT_DIR/server.csr" \
  -subj "/CN=localhost/O=Q-AEGIS Dev/C=US"
openssl x509 -req -in "$CERT_DIR/server.csr" -CA "$CERT_DIR/ca.crt" \
  -CAkey "$CERT_DIR/ca.key" -CAcreateserial -out "$CERT_DIR/server.crt" \
  -days 825 -sha256 -extfile "$CERT_DIR/server.ext"

# server.key: host file may be world-readable on Windows bind mounts; compose
# copies it into the Postgres container and chmod 0600 there. Redis/API tolerate
# looser host modes. Keep ca.key host-only (600).
chmod 644 "$CERT_DIR/server.key" "$CERT_DIR/server.crt" "$CERT_DIR/ca.crt"
chmod 600 "$CERT_DIR/ca.key"
[[ -f "$CERT_DIR/redis.dh" ]] || openssl dhparam -out "$CERT_DIR/redis.dh" 2048
rm -f "$CERT_DIR/server.csr" "$CERT_DIR/ca.srl"

echo "Done. Trust infra/certs/ca.crt for https://127.0.0.1:8443"
