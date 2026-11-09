import unittest
from datetime import datetime, timezone

from sensor_monitor.monitor import TelemetryMonitor
from sensor_monitor.protocol import Telemetry, encode_telemetry


class MonitorTests(unittest.TestCase):
    def test_packet_loss_and_threshold_events_are_reported(self):
        monitor = TelemetryMonitor()
        monitor.ingest(encode_telemetry(Telemetry(10, 25.0, 0.1)))
        monitor.ingest(encode_telemetry(Telemetry(12, 25.1, 0.72)))
        state = monitor.snapshot()
        self.assertEqual(state["errors"]["missing_packets"], 1)
        self.assertEqual(state["received_packets"], 2)
        self.assertEqual(state["status"], "alarm")
        self.assertEqual(state["alarms"][-1]["kind"], "vibration")

    def test_invalid_frame_is_counted_without_stopping_ingestion(self):
        monitor = TelemetryMonitor()
        self.assertFalse(monitor.ingest(b"damaged"))
        self.assertEqual(monitor.snapshot()["errors"]["invalid_frames"], 1)
        self.assertTrue(monitor.ingest(encode_telemetry(Telemetry(0, 22, 0.1))))
        self.assertIsNone(monitor.snapshot()["errors"]["last_error"])

    def test_history_is_bounded(self):
        monitor = TelemetryMonitor(history_limit=2)
        for sequence in range(3):
            monitor.add_telemetry(Telemetry(sequence, 23, 0.1))
        self.assertEqual([row["sequence"] for row in monitor.snapshot()["history"]], [1, 2])

    def test_naive_replay_timestamp_is_rejected(self):
        monitor = TelemetryMonitor()
        with self.assertRaisesRegex(ValueError, "timezone"):
            monitor.add_telemetry(Telemetry(0, 23, 0.1), datetime(2026, 1, 1))

    def test_valid_sample_clears_source_error(self):
        monitor = TelemetryMonitor()
        monitor.mark_source_error("COM port unavailable")
        self.assertEqual(monitor.snapshot()["status"], "error")
        monitor.add_telemetry(Telemetry(0, 23, 0.1))
        self.assertEqual(monitor.snapshot()["status"], "online")


if __name__ == "__main__":
    unittest.main()
