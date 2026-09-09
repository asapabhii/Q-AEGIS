"""Crypto-agile protection engine, ``SPEC.md`` 3.7, implements ``PRD.md`` FR-6.

Phase 2 ships a score-to-profile stub in :mod:`app.crypto.selector`. It does
not persist, does not take a ``trust_score_id``, and does not write an audit
entry. Real trust-score-driven selection, with those three, is Phase 3.

SECURITY CAVEAT, restate this in every docstring in this package: liboqs is NOT
independently audited, and OQS-OpenSSL is documented by its own maintainers as
development and interop-testing only, not production-supported. Do not claim
audited-grade or FIPS-certified guarantees that the library does not back up.

Key management this phase is environment-configured secrets, NOT a hardware
security module (``PRD.md`` NG5). Document that as the current limitation
wherever this module's guarantees are described; never imply hardware-backed
protection that does not exist.

Three protection profiles (parameter tables: ``SPEC.md`` Section 6, do not
guess these values):

- AES-256: AES-256-GCM, classical baseline.
- Hybrid: ``X25519MLKEM768`` exactly, the named group already deployed in
  production TLS 1.3. X25519 ECDH and ML-KEM-768 combine into one shared secret,
  so security holds if either algorithm alone is broken. This is the default
  rather than full post-quantum everywhere.
- Full post-quantum: ML-KEM-1024 (NIST level 5) for key encapsulation, ML-DSA-87
  for signatures, via ``liboqs-python``.

Never use the retired names CRYSTALS-Kyber or CRYSTALS-Dilithium. Use ML-KEM and
ML-DSA. Pin the exact ``liboqs-python`` version and re-run the full crypto test
suite after any version bump; this library's API has changed before.

Owner: Udhav. Required reviewer on any change here, regardless of author.
"""
