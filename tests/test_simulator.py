import queue
import threading
import unittest

from sensor_monitor.protocol import decode_telemetry
from sensor_monitor.simulator import SimulatedSensors, produce_uart_frames


class SimulatorTests(unittest.TestCase):
    def test_seeded_sensors_are_reproducible(self):
        first = SimulatedSensors(seed=7).read(3, 1.5)
        second = SimulatedSensors(seed=7).read(3, 1.5)
        self.assertEqual(first, second)

    def test_demo_injects_one_visible_vibration_event(self):
        reading = SimulatedSensors().read(12, 6.0)
        self.assertEqual(reading.vibration_g, 0.72)

    def test_simulator_transmits_decodable_uart_frames(self):
        frames = queue.Queue()
        stop = threading.Event()
        producer = threading.Thread(target=produce_uart_frames, args=(frames, stop, 0.01))
        producer.start()
        try:
            frame = frames.get(timeout=1)
        finally:
            stop.set()
            producer.join(timeout=1)
        self.assertEqual(decode_telemetry(frame).sequence, 0)


if __name__ == "__main__":
    unittest.main()
