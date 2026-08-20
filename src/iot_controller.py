"""PC-side orchestrator for the IoT final project.

Responsibilities
----------------
* Maintain serial links to ESP32-CAM and Arduino.
* Receive text events and JPEG frames from the ESP32-CAM UART stream.
* Translate natural-language commands into the A..L command alphabet via an LLM.
* Route commands to the correct microcontroller.
* Optionally accept Telegram text/voice messages.

Secrets and machine-specific settings are loaded from environment variables; see
`.env.example`. This file intentionally contains no API keys or bot tokens.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import serial
import soundfile as sf
import speech_recognition as sr
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from telegram import Update
from telegram.ext import Application, CallbackContext, MessageHandler, filters


START_MARKER = b"START_IMG"
END_MARKER = b"END_IMG"
ESP_COMMANDS = set("ABCDEF")
ARDUINO_COMMANDS = set("GHIJKL")
VALID_COMMANDS = ESP_COMMANDS | ARDUINO_COMMANDS

SYSTEM_PROMPT = """You are the command parser for an IoT control system.
Return ONLY one or more command letters separated by spaces.

ESP32-CAM outputs:
A = ESP32 LED 1 ON
B = ESP32 LED 1 OFF
C = ESP32 LED 2 ON
D = ESP32 LED 2 OFF
E = ESP32 LED 3 ON (reserved; not wired in the supplied prototype)
F = ESP32 LED 3 OFF (reserved; not wired in the supplied prototype)

Arduino outputs:
G = Arduino LED 1 ON
H = Arduino LED 1 OFF
I = Arduino LED 2 ON
J = Arduino LED 2 OFF
K = buzzer ON
L = buzzer OFF

Do not output explanations, punctuation, or any token outside A..L.
"""


@dataclass(frozen=True)
class Config:
    esp32_port: str
    arduino_port: str
    baud_rate: int
    llm_model: str
    llm_base_url: str
    llm_api_key: str
    telegram_bot_token: str
    image_output_dir: Path

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        required = ["LLM_API_KEY", "TELEGRAM_BOT_TOKEN"]
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise RuntimeError(
                "Missing required environment variable(s): " + ", ".join(missing)
            )

        return cls(
            esp32_port=os.getenv("ESP32_PORT", "COM13"),
            arduino_port=os.getenv("ARDUINO_PORT", "COM4"),
            baud_rate=int(os.getenv("BAUD_RATE", "115200")),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.avalai.ir/v1"),
            llm_api_key=os.environ["LLM_API_KEY"],
            telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            image_output_dir=Path(os.getenv("IMAGE_OUTPUT_DIR", "data/captures")),
        )


class IoTController:
    """Coordinates ESP32-CAM, Arduino, LLM, Telegram, and frame reception."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.config.image_output_dir.mkdir(parents=True, exist_ok=True)

        self.esp_serial = serial.Serial(
            config.esp32_port, config.baud_rate, timeout=0.2
        )
        self.esp_serial.dtr = False
        self.esp_serial.rts = False
        time.sleep(2)

        self.arduino_serial = serial.Serial(
            config.arduino_port, config.baud_rate, timeout=0.2
        )

        self.llm = ChatOpenAI(
            model=config.llm_model,
            base_url=config.llm_base_url,
            api_key=config.llm_api_key,
        )
        self.recognizer = sr.Recognizer()

        self.telegram_enabled = False
        self.telegram_started = False
        self.login_successful = False
        self.config_complete = False
        self.rx_buffer = bytearray()

    # ------------------------------------------------------------------
    # Command interpretation and routing
    # ------------------------------------------------------------------
    def interpret_command(self, text: str) -> list[str]:
        """Use the LLM only as a constrained natural-language-to-command mapper."""
        response = self.llm.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ]
        )
        tokens = response.content.strip().split()
        return [token for token in tokens if token in VALID_COMMANDS]

    def route_commands(self, commands: Iterable[str]) -> None:
        for command in commands:
            if command in ESP_COMMANDS:
                self.esp_serial.write(command.encode("ascii"))
                print(f"[route] ESP32 <- {command}")
            elif command in ARDUINO_COMMANDS:
                self.arduino_serial.write(command.encode("ascii"))
                print(f"[route] Arduino <- {command}")

    def process_user_text(self, text: str) -> None:
        if not text or not text.strip():
            return
        commands = self.interpret_command(text.strip())
        if not commands:
            print("[llm] No valid command returned.")
            return
        self.route_commands(commands)

    # ------------------------------------------------------------------
    # Telegram voice/text interface
    # ------------------------------------------------------------------
    def audio_to_text(self, audio_path: Path) -> str:
        try:
            with sr.AudioFile(str(audio_path)) as source:
                self.recognizer.adjust_for_ambient_noise(source)
                audio = self.recognizer.record(source)
            return self.recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as exc:
            print(f"[speech] Recognition service error: {exc}")
            return ""

    @staticmethod
    def ogg_to_wav(ogg_file: Path, wav_file: Path) -> None:
        data, samplerate = sf.read(str(ogg_file))
        sf.write(str(wav_file), data, samplerate)

    async def handle_telegram_message(
        self, update: Update, context: CallbackContext
    ) -> None:
        if not update.message:
            return

        text = ""
        if update.message.voice:
            chat_id = update.effective_chat.id
            ogg_path = Path(f"{chat_id}_voice.ogg")
            wav_path = Path(f"{chat_id}_voice.wav")
            telegram_file = await context.bot.get_file(update.message.voice.file_id)
            await telegram_file.download_to_drive(str(ogg_path))
            try:
                self.ogg_to_wav(ogg_path, wav_path)
                text = self.audio_to_text(wav_path)
            finally:
                ogg_path.unlink(missing_ok=True)
                wav_path.unlink(missing_ok=True)

            if text:
                await update.message.reply_text(f"Transcribed text: {text}")
            else:
                await update.message.reply_text("Voice message could not be transcribed.")
                return
        elif update.message.text:
            text = update.message.text
            first_name = update.effective_user.first_name if update.effective_user else "user"
            await update.message.reply_text(f"Hello {first_name}, command received.")
        else:
            return

        if self.telegram_enabled:
            self.process_user_text(text)

    def _run_telegram_bot(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app = Application.builder().token(self.config.telegram_bot_token).build()
        app.add_handler(
            MessageHandler(filters.TEXT | filters.VOICE, self.handle_telegram_message)
        )
        print("[telegram] Bot is running.")
        try:
            # stop_signals=None avoids installing signal handlers in this worker thread.
            app.run_polling(stop_signals=None)
        finally:
            loop.close()

    def start_telegram_bot_once(self) -> None:
        if not self.telegram_enabled or self.telegram_started:
            return
        self.telegram_started = True
        threading.Thread(target=self._run_telegram_bot, daemon=True).start()

    # ------------------------------------------------------------------
    # ESP32 mixed text/binary UART stream
    # ------------------------------------------------------------------
    def save_image(self, payload: bytes) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.config.image_output_dir / f"esp32_image_{timestamp}.jpg"
        path.write_bytes(payload)
        print(f"[camera] Saved {len(payload)} bytes -> {path}")
        return path

    def handle_esp_text(self, raw: bytes) -> None:
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return
        print(f"[esp32] {text}")

        if text == "CONFIG_COMPLETE":
            self.config_complete = True
            return
        if text == "Signed in! Telegram bot reading enabled!":
            self.login_successful = True
            self.telegram_enabled = True
            self.start_telegram_bot_once()
            return
        if text == "Signed in!":
            self.login_successful = True
            self.telegram_enabled = False
            return
        if text == "Invalid credentials. Try again.":
            # Audible feedback from the Arduino buzzer.
            self.arduino_serial.write(b"K")
            time.sleep(0.5)
            self.arduino_serial.write(b"L")
            return

        # Messages entered through the authenticated ESP32 webpage become
        # natural-language device commands after login.
        if self.login_successful:
            ignored_prefixes = (
                "Starting image transmission",
                "Image transmission complete",
            )
            if not text.startswith(ignored_prefixes):
                self.process_user_text(text)

    def consume_esp_bytes(self, data: bytes) -> None:
        """Parse arbitrary chunks containing newline-delimited text and framed JPEGs.

        Frame format: START_IMG | uint32 little-endian length | JPEG | END_IMG
        """
        self.rx_buffer.extend(data)

        while self.rx_buffer:
            start = self.rx_buffer.find(START_MARKER)

            if start == -1:
                newline = self.rx_buffer.find(b"\n")
                if newline == -1:
                    # Keep a bounded tail in case a marker is split across reads.
                    max_tail = max(len(START_MARKER) - 1, 512)
                    if len(self.rx_buffer) > max_tail:
                        chunk = bytes(self.rx_buffer[:-max_tail])
                        del self.rx_buffer[:-max_tail]
                        self.handle_esp_text(chunk)
                    return
                line = bytes(self.rx_buffer[: newline + 1])
                del self.rx_buffer[: newline + 1]
                self.handle_esp_text(line)
                continue

            if start > 0:
                prefix = bytes(self.rx_buffer[:start])
                del self.rx_buffer[:start]
                for line in prefix.splitlines():
                    self.handle_esp_text(line)
                continue

            header_len = len(START_MARKER) + 4
            if len(self.rx_buffer) < header_len:
                return

            size = int.from_bytes(
                self.rx_buffer[len(START_MARKER) : header_len], "little"
            )
            expected_total = header_len + size + len(END_MARKER)
            if len(self.rx_buffer) < expected_total:
                return

            end_start = header_len + size
            if self.rx_buffer[end_start:expected_total] != END_MARKER:
                print("[camera] Frame footer mismatch; resynchronizing UART parser.")
                del self.rx_buffer[0]
                continue

            image = bytes(self.rx_buffer[header_len:end_start])
            del self.rx_buffer[:expected_total]
            self.save_image(image)

    def run(self) -> None:
        print(
            f"[serial] ESP32={self.config.esp32_port}, "
            f"Arduino={self.config.arduino_port}, baud={self.config.baud_rate}"
        )
        try:
            while True:
                waiting = self.esp_serial.in_waiting
                data = self.esp_serial.read(waiting or 1)
                if data:
                    self.consume_esp_bytes(data)
        except KeyboardInterrupt:
            print("\n[main] Stopping.")
        finally:
            self.esp_serial.close()
            self.arduino_serial.close()


def main() -> None:
    controller = IoTController(Config.from_env())
    controller.run()


if __name__ == "__main__":
    main()
