"""Thread-safe telemetry ingestion, health counters, and threshold alarms."""

from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .protocol import PacketError, Telemetry, decode_telemetry, encode_telemetry


@dataclass(frozen=True, slots=True)
class Reading:
    sequence: int
    received_at: str
    temperature_c: float
    vibration_g: float


class TelemetryMonitor:
    """Store a bounded reading history and report malformed frames and alarms."""

    def __init__(self, history_limit: int = 300, temperature_limit_c: float = 60.0,
                 vibration_limit_g: float = 0.5) -> None:
        if not isinstance(history_limit, int) or isinstance(history_limit, bool) or history_limit < 1:
            raise ValueError("history_limit must be at least 1")
        if (
            not math.isfinite(temperature_limit_c)
            or not math.isfinite(vibration_limit_g)
            or temperature_limit_c <= 0
            or vibration_limit_g <= 0
        ):
            raise ValueError("alarm limits must be positive")
        self._history: deque[Reading] = deque(maxlen=history_limit)
        self._temperature_limit = temperature_limit_c
        self._vibration_limit = vibration_limit_g
        self._lock = threading.Lock()
        self._invalid_frames = 0
        self._received_packets = 0
        self._missing_packets = 0
        self._out_of_order_packets = 0
        self._last_sequence: int | None = None
        self._last_error: str | None = None
        self._source_error: str | None = None
        self._alarms: deque[dict[str, str | int | float]] = deque(maxlen=50)

    def ingest(self, packet: bytes, received_at: datetime | None = None) -> bool:
        """Decode and record a frame; malformed frames are counted without killing the receiver."""
        try:
            telemetry = decode_telemetry(packet)
        except PacketError as error:
            with self._lock:
                self._invalid_frames += 1
                self._last_error = str(error)
            return False
        return self.add_telemetry(telemetry, received_at)

    def add_telemetry(self, telemetry: Telemetry,
                      received_at: datetime | None = None) -> bool:
        """Record an already-decoded sample, as used by deterministic CSV replay."""
        # Reuse wire-format checks so replayed records obey the same bounds as live packets.
        telemetry = decode_telemetry(encode_telemetry(telemetry))
        timestamp = received_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("received_at must include a timezone")
        reading = Reading(
            sequence=telemetry.sequence,
            received_at=timestamp.astimezone(timezone.utc).isoformat(),
            temperature_c=telemetry.temperature_c,
            vibration_g=telemetry.vibration_g,
        )
        with self._lock:
            if self._last_sequence is not None:
                gap = (telemetry.sequence - self._last_sequence - 1) & 0xFFFFFFFF
                if 0 < gap < 0x80000000:
                    self._missing_packets += gap
                elif gap >= 0x80000000:
                    self._out_of_order_packets += 1
            self._last_sequence = telemetry.sequence
            self._history.append(reading)
            self._received_packets += 1
            self._source_error = None
            if telemetry.temperature_c >= self._temperature_limit:
                self._alarms.append({
                    "sequence": telemetry.sequence,
                    "kind": "temperature",
                    "value": telemetry.temperature_c,
                })
            if telemetry.vibration_g >= self._vibration_limit:
                self._alarms.append({
                    "sequence": telemetry.sequence,
                    "kind": "vibration",
                    "value": telemetry.vibration_g,
                })
            self._last_error = None
        return True

    def mark_source_error(self, message: str) -> None:
        """Expose an optional serial-source failure while keeping the dashboard alive."""
        with self._lock:
            self._source_error = message

    def snapshot(self) -> dict[str, object]:
        """Return JSON-serializable dashboard state under one consistent lock."""
        with self._lock:
            history = [asdict(reading) for reading in self._history]
            latest = history[-1] if history else None
            if self._source_error:
                status = "error"
            elif latest is None:
                status = "waiting"
            elif (
                latest["temperature_c"] >= self._temperature_limit
                or latest["vibration_g"] >= self._vibration_limit
            ):
                status = "alarm"
            else:
                status = "online"
            return {
                "status": status,
                "latest": latest,
                "history": history,
                "received_packets": self._received_packets,
                "alarms": list(self._alarms),
                "errors": {
                    "invalid_frames": self._invalid_frames,
                    "missing_packets": self._missing_packets,
                    "out_of_order_packets": self._out_of_order_packets,
                    "last_error": self._last_error,
                    "source_error": self._source_error,
                },
            }
