---
applyTo: "backend/app/crypto/**"
---

Read `SPEC.md` Section 6 in full before writing anything in this folder.

- Three protection profiles only: AES-256-GCM (classical), X25519MLKEM768 (hybrid, exact named group, do not substitute a different pairing), ML-KEM-1024 plus ML-DSA-87 (full post-quantum). Use these exact names, never the retired CRYSTALS-Kyber/Dilithium naming.
- `liboqs-python`, version pinned in `requirements.txt`. Re-run the full crypto test suite after any version bump.
- Every function and module docstring in this folder states plainly that liboqs is not independently audited. This is a required, repeated caveat, not boilerplate to trim.
- ML-DSA signing has randomized, hedged signing with variable execution time by design, a fault-injection defense. Do not optimize this into constant-time behavior.
- Key management this phase is environment-configured secrets, not a hardware security module. Do not write code or comments implying HSM-backed protection that doesn't exist.
- Every profile-selection decision writes one row to `crypto_profiles`, referencing the specific `trust_score_id` that drove it.
