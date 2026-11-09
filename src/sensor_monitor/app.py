"""CLI entry point for the ESP32 telemetry simulator and monitoring dashboard."""

from __future__ import annotations

import argparse
import math
import queue
import threading
from pathlib import Path

from .dashboard import serve_dashboard
from .monitor import TelemetryMonitor
from .replay import load_replay_csv
from .serial_link import receive_serial
from .simulator import produce_uart_frames


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor a simulated or replayed embedded sensor node.")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind address (default: loopback only)")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port (default: 8765)")
    parser.add_argument("--interval", type=float, default=0.5, help="simulation sample interval in seconds")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--replay", type=Path, help="show a telemetry CSV instead of starting simulation")
    source.add_argument("--serial-port", help="read live ESP32 UART frames from a COM port (requires pySerial)")
    parser.add_argument("--history", type=int, default=300, help="maximum live readings kept in memory")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("--interval must be positive and finite")
    try:
        monitor = TelemetryMonitor(history_limit=args.history)
        if args.replay:
            rows = load_replay_csv(args.replay)
            for telemetry, timestamp in rows:
                monitor.add_telemetry(telemetry, timestamp)
            print(f"Loaded {len(rows)} replay samples from {args.replay.name}")

        server = serve_dashboard(monitor, args.host, args.port)
        stop = threading.Event()
        uart_frames: queue.Queue[bytes] = queue.Queue()
        producer: threading.Thread | None = None
        receiver: threading.Thread | None = None
        if args.serial_port:
            def receive_from_com_port() -> None:
                try:
                    receive_serial(args.serial_port, monitor.ingest, stop)
                except (OSError, RuntimeError) as error:
                    monitor.mark_source_error(str(error))
                    print(f"Serial source error: {error}")

            receiver = threading.Thread(target=receive_from_com_port, daemon=True)
            receiver.start()
        elif args.replay is None:
            producer = threading.Thread(
                target=produce_uart_frames, args=(uart_frames, stop, args.interval), daemon=True
            )

            def receive_uart() -> None:
                while not stop.is_set() or not uart_frames.empty():
                    try:
                        packet = uart_frames.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    monitor.ingest(packet)

            receiver = threading.Thread(target=receive_uart, daemon=True)
            producer.start()
            receiver.start()

        address, port = server.server_address[:2]
        print(f"Dashboard running at http://{address}:{port}/ (press Ctrl+C to stop)")
        try:
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            print("Stopping sensor monitor...")
        finally:
            stop.set()
            server.server_close()
            if producer:
                producer.join(timeout=2)
            if receiver:
                receiver.join(timeout=2)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
