"""Trigger an ESP32-CAM capture through its local web interface.

Important: the `/capture` endpoint confirms the request with HTML; the JPEG is
transported to the PC over UART and saved by `src/iot_controller.py`.
"""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    ip = os.getenv("ESP32_AP_IP", "192.168.4.1")
    username = os.getenv("ESP32_WEB_USERNAME", "admin")
    password = os.getenv("ESP32_WEB_PASSWORD", "change-me")

    session = requests.Session()
    login = session.post(
        f"http://{ip}/",
        data={"username": username, "password": password, "bot_enabled": "on"},
        timeout=5,
        allow_redirects=True,
    )
    login.raise_for_status()

    if "Invalid credentials" in login.text:
        raise RuntimeError("ESP32 web login failed")

    capture = session.get(f"http://{ip}/capture", timeout=10)
    capture.raise_for_status()
    print("Capture requested. Watch the PC controller for the saved JPEG path.")


if __name__ == "__main__":
    main()
