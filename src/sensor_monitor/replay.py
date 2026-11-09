"""Strict CSV replay loader for representative telemetry traces."""

from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .protocol import Telemetry

_HEADERS = {"sequence", "elapsed_s", "temperature_c", "vibration_g"}


def load_replay_csv(path: str | Path) -> list[tuple[Telemetry, datetime]]:
    """Load ordered synthetic or recorded telemetry rows with relative timestamps."""
    readings: list[tuple[Telemetry, datetime]] = []
    try:
        with Path(path).open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or not _HEADERS.issubset(reader.fieldnames):
                raise ValueError(f"replay CSV must contain columns: {', '.join(sorted(_HEADERS))}")
            previous_elapsed = -math.inf
            for line, row in enumerate(reader, start=2):
                try:
                    sequence = int(row["sequence"])
                    elapsed = float(row["elapsed_s"])
                    temperature = float(row["temperature_c"])
                    vibration = float(row["vibration_g"])
                except (TypeError, ValueError) as error:
                    raise ValueError(f"invalid telemetry value on CSV line {line}") from error
                if not 0 <= sequence <= 0xFFFFFFFF or elapsed < 0 or vibration < 0 or not all(map(math.isfinite, (elapsed, temperature, vibration))):
                    raise ValueError(f"CSV line {line} contains an invalid or non-finite value")
                if elapsed <= previous_elapsed:
                    raise ValueError("elapsed_s values must be strictly increasing")
                previous_elapsed = elapsed
                received_at = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=elapsed)
                readings.append((Telemetry(sequence, temperature, vibration), received_at))
    except OSError:
        raise
    except csv.Error as error:
        raise ValueError(f"could not parse replay CSV: {error}") from error
    if not readings:
        raise ValueError("replay CSV must contain at least one telemetry row")
    return readings
