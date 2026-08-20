# Changelog

## Repository-ready edition

- Added structured documentation and architecture figures.
- Removed hard-coded API/bot secrets and introduced `.env.example`.
- Introduced `secrets.h.example` for ESP32 AP/web credentials.
- Refactored the PC controller into a single incremental serial parser.
- Standardized camera frame length to `uint32_t` little-endian.
- Corrected the PC capture helper to treat `/capture` as a trigger/confirmation endpoint.
- Added explicit LLM output validation and command routing.
- Documented reserved ESP32 commands `E/F`.
- Converted the supplied hard-coded DeepFace example into a reusable CLI utility.
- Added `.gitignore` rules for secrets, captures, audio, and biometric reference data.
