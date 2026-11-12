
# MasoMlimi security (district pilot)

## Cryptography in use
- **HMAC-SHA256** pack signatures (`MASOMLIMI_PACK_SECRET` or `MASOMLIMI_API_KEY`) via `GET /v1/procedures/signed`
- **Constant-time** API key compare (`hmac.compare_digest`) when `MASOMLIMI_API_KEY` is set
- **Device id hashing** (SHA-256 + salt) for scan telemetry — raw device ids not stored in scan analytics
- **Optional Fernet** at-rest encryption when `MASOMLIMI_DATA_KEY` is set (`security.encrypt_blob`)
- Security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`

## Required before public internet
- TLS (HTTPS) reverse proxy — do not expose cleartext HTTP on the public internet
- Rotate `MASOMLIMI_API_KEY` and `MASOMLIMI_PACK_SECRET`
- Independent penetration test
- Expert portal behind auth / VPN

## Env vars
```
MASOMLIMI_API_KEY=long-random
MASOMLIMI_PACK_SECRET=long-random
MASOMLIMI_DATA_KEY=optional-passphrase-for-fernet
MASOMLIMI_PRIVACY_SALT=optional-salt
```
