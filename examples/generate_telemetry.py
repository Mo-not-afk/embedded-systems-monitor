"""Regenerate the clearly synthetic ESP32 telemetry replay trace."""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path


def main() -> None:
    randomizer = random.Random(2026)
    output = Path(__file__).parent / "data" / "sensor_telemetry.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sequence", "elapsed_s", "temperature_c", "vibration_g"])
        for sequence in range(80):
            elapsed = sequence * 0.5
            temperature = 24 + 0.025 * elapsed + randomizer.gauss(0, 0.04)
            vibration = 0.11 + 0.025 * math.sin(2 * math.pi * 1.5 * elapsed) + randomizer.gauss(0, 0.006)
            if sequence == 12:
                vibration = 0.72
            writer.writerow([sequence, f"{elapsed:.1f}", f"{temperature:.3f}", f"{max(0, vibration):.3f}"])
    print(f"Wrote 80 synthetic telemetry rows to {output}")


if __name__ == "__main__":
    main()
