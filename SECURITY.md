# Security and Privacy Notes

This repository represents an educational IoT prototype. Treat the following as mandatory before public deployment or a public GitHub push.

## Rotate previously embedded credentials

The private source supplied for repository preparation included hard-coded credentials for an LLM endpoint and a Telegram bot. They are not copied into this repository. Because credentials that have existed in source code may have been exposed elsewhere, **revoke/rotate them before publishing** and place only the replacements in your local `.env`.

## Never commit these files/data

- `.env`
- `firmware/esp32_cam/secrets.h`
- captured voice files
- captured camera images unless intentionally anonymized
- reference face images or face embeddings

The provided `.gitignore` excludes them by default.

## Web interface scope

The ESP32-CAM serves plain HTTP on its local access point. Credentials and commands therefore lack transport encryption. This can be acceptable for a closed laboratory demo, but it is not appropriate for an untrusted network. For a real deployment, use a trusted gateway, TLS termination, stronger authentication, session isolation, rate limiting, and audit logging.

## LLM command safety

The LLM is used only as a constrained natural-language parser. The PC validates the returned tokens against a fixed command set (`A..L`) before writing to serial. Production systems should additionally add acknowledgements, authorization by user/device, state-aware checks, timeouts, and a deterministic fallback parser for critical operations.

## Biometric data

Face images are sensitive personal data. Obtain consent, minimize retention, protect reference images, and do not use the optional DeepFace script as the sole access-control mechanism without proper liveness detection, dataset evaluation, and a privacy/security review.
