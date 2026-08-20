# Source Provenance and Repository Cleanup

The repository-ready edition was reconstructed from the following project materials supplied for the course submission:

- `IoT.py` — PC-side serial, Telegram, speech, and LLM orchestration
- `Tel_Iot.py` — ESP32 web-login/capture helper
- `Arduino_IOT.ino` — Arduino LED/buzzer actuator code
- `ESP-AC-IOT.ino` — ESP32-CAM web server, camera, LEDs, and UART image transfer
- `Face_Rec.py` — standalone DeepFace verification example

The public edition deliberately does not copy embedded service credentials from the submitted prototype. It also consolidates the two image-reception paths, fixes the capture-helper protocol mismatch, parameterizes local paths/settings, and documents behaviors that were present but incomplete (notably reserved commands `E/F`).

These cleanup changes are intended to improve reproducibility, safety, and maintainability while preserving the central project architecture and command semantics.
