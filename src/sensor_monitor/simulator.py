"""Reproducible sensor and UART simulation used when hardware is unavailable."""

from __future__ import annotations

import math
import queue
import random
import threading
import time

from .protocol import Telemetry, encode_telemetry


class SimulatedSensors:
    """Generate room-temperature and motor-vibration readings with seeded noise."""

    def __init__(self, seed: int = 2026) -> None:
        self._random = random.Random(seed)

    def read(self, sequence: int, elapsed_seconds: float) -> Telemetry:
        if sequence < 0 or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("sequence and elapsed time must be non-negative")
        temperature = 24.0 + 0.025 * elapsed_seconds + self._random.gauss(0, 0.04)
        vibration = 0.11 + 0.025 * math.sin(2 * math.pi * 1.5 * elapsed_seconds)
        vibration += self._random.gauss(0, 0.006)
        # A single injected excursion makes the alarm path visible in a short demo run.
        if sequence == 12:
            vibration = 0.72
        return Telemetry(sequence, temperature, max(0.0, vibration))


def produce_uart_frames(output: queue.Queue[bytes], stop: threading.Event,
                        interval_seconds: float = 0.5, seed: int = 2026) -> None:
    """Simulate a node periodically transmitting framed UART telemetry."""
    if not math.isfinite(interval_seconds) or interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive and finite")
    sensors = SimulatedSensors(seed)
    started = time.monotonic()
    sequence = 0
    while not stop.is_set():
        sample = sensors.read(sequence, time.monotonic() - started)
        output.put(encode_telemetry(sample))
        sequence = (sequence + 1) & 0xFFFFFFFF
        stop.wait(interval_seconds)
