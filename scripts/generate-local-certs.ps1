# Generate local self-signed TLS material for Q-AEGIS Shield.
# Output: infra/certs/ (gitignored). Never commit these files.
#
# Uses openssl from PATH, or Git for Windows' bundled openssl if PATH
# does not include it (common on Windows).
#
# Usage (from repo root, PowerShell):
#   .\scripts\generate-local-certs.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$CertDir = Join-Path $Root "infra\certs"

function Resolve-OpenSsl {
    $cmd = Get-Command openssl -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        "C:\Program Files\Git\usr\bin\openssl.exe",
        "C:\Program Files\Git\mingw64\bin\openssl.exe",
        "C:\Program Files (x86)\Git\usr\bin\openssl.exe",
        "C:\Program Files (x86)\Git\mingw64\bin\openssl.exe"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    throw @"
openssl was not found on PATH and Git for Windows was not detected.

Install Git for Windows (includes openssl), or add openssl to PATH, then re-run:
  .\scripts\generate-local-certs.ps1

You can skip TLS for now and run the API with plain HTTP:
  cd backend; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"@
}

$OpenSsl = Resolve-OpenSsl
Write-Host "Using openssl: $OpenSsl"

New-Item -ItemType Directory -Force -Path $CertDir | Out-Null

$CaKey = Join-Path $CertDir "ca.key"
$CaCrt = Join-Path $CertDir "ca.crt"
$ServerKey = Join-Path $CertDir "server.key"
$ServerCrt = Join-Path $CertDir "server.crt"
$ServerCsr = Join-Path $CertDir "server.csr"
$ExtFile = Join-Path $CertDir "server.ext"
$DhParam = Join-Path $CertDir "redis.dh"

Write-Host "Writing certs to $CertDir"

# Prior runs may have left keys read-only (Postgres ACL hardening). Unlock first.
foreach ($path in @($CaKey, $ServerKey, $CaCrt, $ServerCrt)) {
  if (Test-Path $path) {
    icacls $path /grant:r "${env:USERNAME}:(F)" | Out-Null
    attrib -R $path | Out-Null
  }
}

& $OpenSsl genrsa -out $CaKey 4096
& $OpenSsl req -x509 -new -nodes -key $CaKey -sha256 -days 825 -out $CaCrt `
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

& $OpenSsl genrsa -out $ServerKey 2048
& $OpenSsl req -new -key $ServerKey -out $ServerCsr `
  -subj "/CN=localhost/O=Q-AEGIS Dev/C=US"
& $OpenSsl x509 -req -in $ServerCsr -CA $CaCrt -CAkey $CaKey -CAcreateserial `
  -out $ServerCrt -days 825 -sha256 -extfile $ExtFile

# Redis TLS optionally wants DH params; generate once (slow).
if (-not (Test-Path $DhParam)) {
  Write-Host "Generating DH params (can take a minute)..."
  & $OpenSsl dhparam -out $DhParam 2048
}

# Postgres refuses world-readable key files inside the container.
# Leave the key writable for local regeneration; containers mount read-only.
icacls $ServerKey /inheritance:r | Out-Null
icacls $ServerKey /grant:r "${env:USERNAME}:(R,W)" | Out-Null

Remove-Item $ServerCsr -ErrorAction SilentlyContinue
Remove-Item (Join-Path $CertDir "ca.srl") -ErrorAction SilentlyContinue

Write-Host "Done. Trust infra/certs/ca.crt in the browser for https://127.0.0.1:8443"
Write-Host "Compose expects these files under infra/certs/ before 'docker compose up'."
