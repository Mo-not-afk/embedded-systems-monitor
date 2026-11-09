import unittest

from sensor_monitor.protocol import PacketError, Telemetry, UARTFrameParser, crc16_ccitt, decode_telemetry, encode_telemetry


class ProtocolTests(unittest.TestCase):
    def test_crc16_ccitt_known_check_value(self):
        self.assertEqual(crc16_ccitt(b"123456789"), 0x29B1)

    def test_telemetry_round_trip_matches_wire_resolution(self):
        source = Telemetry(42, 24.376, 0.1234)
        decoded = decode_telemetry(encode_telemetry(source))
        self.assertEqual(decoded.sequence, 42)
        self.assertAlmostEqual(decoded.temperature_c, 24.38)
        self.assertAlmostEqual(decoded.vibration_g, 0.123)

    def test_corrupted_packet_fails_checksum(self):
        frame = bytearray(encode_telemetry(Telemetry(1, 22, 0.1)))
        frame[5] ^= 0x01
        with self.assertRaisesRegex(PacketError, "CRC mismatch"):
            decode_telemetry(bytes(frame))

    def test_bad_frame_length_is_rejected(self):
        with self.assertRaisesRegex(PacketError, "12 bytes"):
            decode_telemetry(b"short")

    def test_sensor_values_must_fit_packet_fields(self):
        with self.assertRaisesRegex(ValueError, "temperature_c"):
            encode_telemetry(Telemetry(0, 400, 0.1))

    def test_stream_parser_handles_partial_frames_and_noise(self):
        parser = UARTFrameParser()
        first = encode_telemetry(Telemetry(1, 22, 0.1))
        second = encode_telemetry(Telemetry(2, 23, 0.2))
        self.assertEqual(parser.feed(b"noise" + first[:5]), [])
        frames = parser.feed(first[5:] + second)
        self.assertEqual([decode_telemetry(frame).sequence for frame in frames], [1, 2])

    def test_stream_parser_resynchronizes_after_corrupt_frame(self):
        parser = UARTFrameParser()
        corrupt = bytearray(encode_telemetry(Telemetry(1, 22, 0.1)))
        corrupt[4] ^= 0x80
        valid = encode_telemetry(Telemetry(2, 23, 0.2))
        frames = parser.feed(bytes(corrupt) + valid)
        self.assertEqual(len(frames), 2)
        with self.assertRaisesRegex(PacketError, "CRC mismatch"):
            decode_telemetry(frames[0])
        self.assertEqual(decode_telemetry(frames[1]).sequence, 2)


if __name__ == "__main__":
    unittest.main()
