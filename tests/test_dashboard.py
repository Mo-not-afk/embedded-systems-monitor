import json
import threading
import unittest
from urllib.request import urlopen

from sensor_monitor.dashboard import serve_dashboard
from sensor_monitor.monitor import TelemetryMonitor
from sensor_monitor.protocol import Telemetry


class DashboardTests(unittest.TestCase):
    def test_local_dashboard_serves_html_and_live_json(self):
        monitor = TelemetryMonitor()
        monitor.add_telemetry(Telemetry(1, 24.5, 0.12))
        server = serve_dashboard(monitor, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            with urlopen(base + "/api/live", timeout=2) as response:
                state = json.loads(response.read())
            with urlopen(base + "/", timeout=2) as response:
                html = response.read().decode("utf-8")
            self.assertEqual(state["latest"]["temperature_c"], 24.5)
            self.assertIn("Embedded Sensor Monitor", html)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
