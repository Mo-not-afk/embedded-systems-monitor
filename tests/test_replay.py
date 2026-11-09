import tempfile
import unittest
from pathlib import Path

from sensor_monitor.monitor import TelemetryMonitor
from sensor_monitor.replay import load_replay_csv


EXAMPLE = Path(__file__).parents[1] / "examples" / "data" / "sensor_telemetry.csv"


class ReplayTests(unittest.TestCase):
    def test_example_trace_loads_and_contains_injected_alarm_event(self):
        rows = load_replay_csv(EXAMPLE)
        self.assertEqual(len(rows), 80)
        monitor = TelemetryMonitor()
        for telemetry, timestamp in rows:
            monitor.add_telemetry(telemetry, timestamp)
        snapshot = monitor.snapshot()
        self.assertTrue(any(event["sequence"] == 12 for event in snapshot["alarms"]))
        self.assertEqual(snapshot["errors"]["missing_packets"], 0)

    def test_replay_rejects_nonincreasing_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text(
                "sequence,elapsed_s,temperature_c,vibration_g\n0,0,22,0.1\n1,0,23,0.2\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "strictly increasing"):
                load_replay_csv(path)


if __name__ == "__main__":
    unittest.main()
