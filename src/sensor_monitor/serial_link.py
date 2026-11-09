"""Optional pySerial bridge for physical ESP32 UART telemetry."""

from __future__ import annotations

import threading
from collections.abc import Callable

from .protocol import UARTFrameParser


def receive_serial(port: str, on_frame: Callable[[bytes], None],
                   stop: threading.Event) -> None:
    """Read 115200-baud ESP32 frames until stopped; requires the serial extra."""
    try:
        import serial
    except ImportError as error:
        raise RuntimeError("serial input requires pySerial; install with `python -m pip install -e '.[serial]'`") from error

    parser = UARTFrameParser()
    try:
        with serial.Serial(port, baudrate=115200, timeout=0.2) as connection:
            while not stop.is_set():
                for frame in parser.feed(connection.read(64)):
                    on_frame(frame)
    except serial.SerialException as error:
        raise OSError(f"could not read telemetry from {port}: {error}") from error
