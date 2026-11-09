"""Compact UART telemetry framing with CRC-16/CCITT error detection."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass

_PAYLOAD = struct.Struct("<2sIhH")
_CRC = struct.Struct("<H")
_MAGIC = b"SM"
FRAME_SIZE = _PAYLOAD.size + _CRC.size


class PacketError(ValueError):
    """Raised when a telemetry frame is malformed or fails its checksum."""


@dataclass(frozen=True, slots=True)
class Telemetry:
    sequence: int
    temperature_c: float
    vibration_g: float


def crc16_ccitt(data: bytes) -> int:
    """Compute CRC-16/CCITT-FALSE (poly 0x1021, init 0xffff)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def encode_telemetry(record: Telemetry) -> bytes:
    """Encode telemetry as magic, sequence, centi-degrees, milli-g, then CRC."""
    if not isinstance(record.sequence, int) or isinstance(record.sequence, bool) or not 0 <= record.sequence <= 0xFFFFFFFF:
        raise ValueError("sequence must be an unsigned 32-bit integer")
    if not math.isfinite(record.temperature_c) or not -327.68 <= record.temperature_c <= 327.67:
        raise ValueError("temperature_c must fit a signed centi-degree field")
    if not math.isfinite(record.vibration_g) or not 0 <= record.vibration_g <= 65.535:
        raise ValueError("vibration_g must fit an unsigned milli-g field")
    payload = _PAYLOAD.pack(
        _MAGIC, record.sequence, round(record.temperature_c * 100), round(record.vibration_g * 1000)
    )
    return payload + _CRC.pack(crc16_ccitt(payload))


def decode_telemetry(packet: bytes) -> Telemetry:
    """Validate a frame and recover its quantized engineering values."""
    if not isinstance(packet, bytes) or len(packet) != _PAYLOAD.size + _CRC.size:
        raise PacketError(f"telemetry frame must contain {_PAYLOAD.size + _CRC.size} bytes")
    payload, checksum_bytes = packet[:-_CRC.size], packet[-_CRC.size:]
    expected_crc = _CRC.unpack(checksum_bytes)[0]
    if crc16_ccitt(payload) != expected_crc:
        raise PacketError("telemetry CRC mismatch")
    magic, sequence, temperature_centi, vibration_milli = _PAYLOAD.unpack(payload)
    if magic != _MAGIC:
        raise PacketError("telemetry frame has an invalid sync marker")
    return Telemetry(sequence, temperature_centi / 100, vibration_milli / 1000)


class UARTFrameParser:
    """Recover fixed-size frames from an arbitrary UART byte stream."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[bytes]:
        """Return complete sync-aligned frames; retain partial data for the next read."""
        self._buffer.extend(chunk)
        frames: list[bytes] = []
        while True:
            sync = self._buffer.find(_MAGIC)
            if sync < 0:
                # A trailing 'S' might be the first byte of a sync marker split across reads.
                keep = 1 if self._buffer.endswith(_MAGIC[:1]) else 0
                if keep:
                    self._buffer[:] = self._buffer[-1:]
                else:
                    self._buffer.clear()
                break
            if sync:
                del self._buffer[:sync]
            if len(self._buffer) < FRAME_SIZE:
                break
            candidate = bytes(self._buffer[:FRAME_SIZE])
            frames.append(candidate)
            if crc16_ccitt(candidate[:-_CRC.size]) == _CRC.unpack(candidate[-_CRC.size:])[0]:
                del self._buffer[:FRAME_SIZE]
            else:
                # Advance one byte after a bad candidate so the next sync can be recovered.
                del self._buffer[0]
        return frames
