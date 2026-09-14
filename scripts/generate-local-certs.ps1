# Generate local self-signed TLS material for Q-AEGIS Shield.
# Output: infra/certs/ (gitignored). Never commit these files.
#
# Requires openssl on PATH (Git for Windows ships one).
#
# Usage (from repo root, PowerShell):
#   .\scripts\generate-local-certs.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$CertDir = Join-Path $Root "infra\certs"

New-Item -ItemType Directory -Force -Path $CertDir | Out-Null

$CaKey = Join-Path $CertDir "ca.key"
$CaCrt = Join-Path $CertDir "ca.crt"
$ServerKey = Join-Path $CertDir "server.key"
$ServerCrt = Join-Path $CertDir "server.crt"
$ServerCsr = Join-Path $CertDir "server.csr"
$ExtFile = Join-Path $CertDir "server.ext"
$DhParam = Join-Path $CertDir "redis.dh"

Write-Host "Writing certs to $CertDir"

openssl genrsa -out $CaKey 4096
openssl req -x509 -new -nodes -key $CaKey -sha256 -days 825 -out $CaCrt `
  -subj "/CN=Q-AEGIS Local CA/O=Q-AEGIS Dev/C=US"

@"
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
"@ | Set-Content -Path $ExtFile -Encoding ascii

openssl genrsa -out $ServerKey 2048
openssl req -new -key $ServerKey -out $ServerCsr `
  -subj "/CN=localhost/O=Q-AEGIS Dev/C=US"
openssl x509 -req -in $ServerCsr -CA $CaCrt -CAkey $CaKey -CAcreateserial `
  -out $ServerCrt -days 825 -sha256 -extfile $ExtFile

# Redis TLS optionally wants DH params; generate once.
if (-not (Test-Path $DhParam)) {
  openssl dhparam -out $DhParam 2048
}

# Postgres refuses world-readable key files inside the container.
icacls $ServerKey /inheritance:r | Out-Null
icacls $ServerKey /grant:r "$env:USERNAME:(R)" | Out-Null

Remove-Item $ServerCsr -ErrorAction SilentlyContinue
Remove-Item (Join-Path $CertDir "ca.srl") -ErrorAction SilentlyContinue

Write-Host "Done. Trust infra/certs/ca.crt in the browser for https://127.0.0.1:8443"
Write-Host "Compose expects these files under infra/certs/ before 'docker compose up'."
