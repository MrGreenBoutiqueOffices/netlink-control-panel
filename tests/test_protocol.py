import unittest

from netlink_panel.protocol import Decoder, ProtocolError, encode


class ProtocolTests(unittest.TestCase):
    def test_fragmented_and_combined_frames(self):
        frame = encode({"type": "heartbeat"})
        decoder = Decoder()
        self.assertEqual(decoder.feed(frame[:8]), [])
        self.assertEqual(len(decoder.feed(frame[8:] + frame)), 2)

    def test_bad_frames_and_boot_logs_do_not_break_next_frame(self):
        decoder = Decoder()
        messages = decoder.feed(b'Booting...\n{"v":2,"type":"hello"}\n[]\n' + encode({"type": "heartbeat"}))
        self.assertEqual(len(messages), 1)
        self.assertEqual(decoder.rejected, 3)

    def test_oversized_frame_is_dropped_until_newline(self):
        decoder = Decoder()
        self.assertEqual(decoder.feed(b"x" * 20000), [])
        self.assertLessEqual(len(decoder.buffer), 1024)
        self.assertEqual(decoder.feed(encode({"type": "heartbeat"})), [])
        self.assertEqual(len(decoder.feed(encode({"type": "heartbeat"}))), 1)

    def test_boolean_and_negative_ids_are_rejected(self):
        for bad_id in (True, 0, -1, 2**31):
            with self.assertRaises(ProtocolError):
                encode({"type": "hello", "id": bad_id})


if __name__ == "__main__":
    unittest.main()
