import unittest
from unittest.mock import Mock

from pphandcontrol.camera import CameraEvent, publish_latest
from pphandcontrol.session import ControlSession
from queue import Queue


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.detector = Mock()
        self.detector.update.return_value = "next"
        self.session = ControlSession(self.detector)

    def event(self, **kwargs):
        return CameraEvent(generation=self.session.generation, timestamp=10.0, **kwargs)

    def test_start_paused_and_refuse_resume_without_camera(self):
        self.assertTrue(self.session.paused)
        self.assertFalse(self.session.toggle())
        self.detector.update.assert_not_called()

    def test_pause_and_resume_clear_swipe_history(self):
        self.session.process(self.event(), now=10.1)
        self.assertTrue(self.session.toggle())
        self.assertEqual(self.session.process(self.event(), now=10.1), "next")
        self.session.toggle()
        self.assertIsNone(self.session.process(self.event(), now=10.1))
        self.assertGreaterEqual(self.detector.reset.call_count, 3)

    def test_camera_failure_pauses_until_fresh_frames_and_manual_resume(self):
        self.session.process(self.event(), now=10.0)
        self.session.toggle()
        self.session.process(self.event(error="unplugged"), now=10.1)
        self.assertTrue(self.session.paused)
        self.assertFalse(self.session.ready)
        self.assertFalse(self.session.toggle())
        self.session.process(self.event(), now=10.1)
        self.assertTrue(self.session.ready)
        self.assertTrue(self.session.paused)

    def test_old_camera_generation_cannot_reactivate_or_navigate(self):
        old = self.event()
        self.session.restart_camera()
        self.session.process(old, now=10.1)
        self.assertFalse(self.session.ready)
        self.detector.update.assert_not_called()

    def test_late_and_future_frames_do_not_emit_commands(self):
        self.session.ready = True
        self.session.toggle()
        self.assertIsNone(self.session.process(self.event(), now=11.0))
        self.assertIsNone(self.session.process(self.event(), now=9.0))
        self.detector.update.assert_not_called()

    def test_stalled_camera_pauses(self):
        self.session.process(self.event(), now=10.0)
        self.session.toggle()
        self.session.check_stale(now=11.1)
        self.assertTrue(self.session.paused)
        self.assertFalse(self.session.ready)

    def test_only_newest_frame_is_retained(self):
        queue = Queue(maxsize=1)
        publish_latest(queue, CameraEvent(0, 1.0))
        publish_latest(queue, CameraEvent(0, 2.0))
        self.assertEqual(queue.qsize(), 1)
        self.assertEqual(queue.get().timestamp, 2.0)


if __name__ == "__main__":
    unittest.main()
