"""Camera-worker integration checks using no camera, model or native libraries."""

from pathlib import Path
from queue import Queue
import sys
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pphandcontrol.camera import CameraEvent, TrackingWorker, publish_latest
from pphandcontrol.gestures import SwipeDetector
from pphandcontrol.session import ControlSession


class CameraWorkerTests(unittest.TestCase):
    def setUp(self):
        self.events = Queue(maxsize=1)
        self.worker = TrackingWorker(3, 7, Path("bundled-model.task"), self.events)
        self.capture = Mock()
        self.capture.isOpened.return_value = True
        self.landmarker = Mock()
        self.landmarker.detect_for_video.return_value = SimpleNamespace(hand_landmarks=[])
        self.cv2 = SimpleNamespace(
            VideoCapture=Mock(return_value=self.capture),
            CAP_DSHOW=700, CAP_MSMF=1400,
            CAP_PROP_FRAME_WIDTH=3, CAP_PROP_FRAME_HEIGHT=4, CAP_PROP_FPS=5,
            COLOR_BGR2RGB=4,
            flip=Mock(side_effect=lambda frame, axis: ("mirrored", frame, axis)),
            cvtColor=Mock(side_effect=lambda frame, code: ("rgb", frame, code)),
        )
        self.base_options = Mock(return_value="base-options")
        self.hand_options = Mock(return_value="hand-options")
        self.factory = Mock(return_value=self.landmarker)
        self.mp = SimpleNamespace(
            tasks=SimpleNamespace(
                BaseOptions=self.base_options,
                vision=SimpleNamespace(
                    HandLandmarkerOptions=self.hand_options,
                    RunningMode=SimpleNamespace(VIDEO="video"),
                    HandLandmarker=SimpleNamespace(create_from_options=self.factory),
                ),
            ),
            Image=Mock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs)),
            ImageFormat=SimpleNamespace(SRGB="srgb"),
        )
        self.modules = patch.dict(sys.modules, {"cv2": self.cv2, "mediapipe": self.mp})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        # Avoid real retry delays while retaining Event.is_set()/set() behavior.
        self.worker.stopping.wait = Mock(return_value=False)

    def stop_after_one_frame(self):
        calls = 0

        def read():
            nonlocal calls
            calls += 1
            if calls == 1:
                return True, "bgr-frame"
            self.worker.stopping.set()
            return False, None

        self.capture.read.side_effect = read

    def test_both_backends_failing_publish_actionable_error_and_release(self):
        first, second = Mock(), Mock()
        first.isOpened.return_value = second.isOpened.return_value = False
        self.cv2.VideoCapture.side_effect = [first, second]
        self.worker.run()
        event = self.events.get_nowait()
        self.assertEqual(event.generation, 7)
        self.assertIn("Camera could not open", event.error)
        self.assertIn("permissions", event.error)
        self.assertIsNone(event.frame)
        first.release.assert_called_once_with()
        second.release.assert_called_once_with()
        self.factory.assert_not_called()
        self.assertEqual(self.cv2.VideoCapture.call_args_list[0].args, (3, 700))
        self.assertEqual(self.cv2.VideoCapture.call_args_list[1].args, (3, 1400))

    def test_failed_first_backend_falls_back_then_stops_cleanly(self):
        first = Mock()
        first.isOpened.return_value = False
        self.cv2.VideoCapture.side_effect = [first, self.capture]
        self.stop_after_one_frame()
        self.worker.run()
        self.assertIsNone(self.events.get_nowait().error)
        first.release.assert_called_once_with()
        self.capture.release.assert_called_once_with()
        self.landmarker.close.assert_called_once_with()

    def test_five_read_failures_publish_error_that_pauses_navigation(self):
        self.capture.read.return_value = (False, None)
        self.worker.run()
        event = self.events.get_nowait()
        self.assertEqual(self.capture.read.call_count, 5)
        self.assertEqual(self.worker.stopping.wait.call_count, 4)
        self.assertIn("Navigation is paused", event.error)
        self.assertIn("Retry camera", event.error)
        session = ControlSession(SwipeDetector())
        session.generation = 7
        session.process(CameraEvent(7, event.timestamp), now=event.timestamp)
        self.assertTrue(session.toggle())
        self.assertFalse(session.paused)
        self.assertIsNone(session.process(event, now=event.timestamp))
        self.assertTrue(session.paused)
        self.assertFalse(session.ready)
        self.assertEqual(session.error, event.error)
        self.capture.release.assert_called_once_with()
        self.landmarker.close.assert_called_once_with()

    def test_transient_failed_reads_recover_without_error(self):
        calls = 0

        def read():
            nonlocal calls
            calls += 1
            if calls <= 2:
                return False, None
            if calls == 3:
                return True, "bgr-frame"
            self.worker.stopping.set()
            return False, None

        self.capture.read.side_effect = read
        self.worker.run()
        event = self.events.get_nowait()
        self.assertIsNone(event.error)
        self.assertEqual(self.landmarker.detect_for_video.call_count, 1)

    def test_mirrors_before_inference_and_preserves_two_hand_mapping(self):
        self.stop_after_one_frame()
        left = [SimpleNamespace(x=index / 30, y=0.3, z=-0.01) for index in range(21)]
        right = [SimpleNamespace(x=0.9 - index / 30, y=0.7, z=0.01) for index in range(21)]
        self.landmarker.detect_for_video.return_value = SimpleNamespace(hand_landmarks=[left, right])
        with patch("pphandcontrol.camera.monotonic", return_value=12.345):
            self.worker.run()
        self.cv2.flip.assert_called_once_with("bgr-frame", 1)
        self.cv2.cvtColor.assert_called_once_with(("mirrored", "bgr-frame", 1), 4)
        image, timestamp_ms = self.landmarker.detect_for_video.call_args.args
        self.assertEqual(image.data, ("rgb", ("mirrored", "bgr-frame", 1), 4))
        self.assertEqual(image.image_format, "srgb")
        self.assertEqual(timestamp_ms, 12345)
        event = self.events.get_nowait()
        self.assertEqual(event.frame, image.data)
        self.assertEqual(len(event.hands), 2)
        self.assertEqual(event.hands[0].points, tuple((p.x, p.y, p.z) for p in left))
        self.assertEqual(event.hands[1].points, tuple((p.x, p.y, p.z) for p in right))
        self.assertTrue(all(hand.timestamp == 12.345 for hand in event.hands))
        self.assertEqual(self.hand_options.call_args.kwargs["num_hands"], 2)
        self.assertEqual(self.hand_options.call_args.kwargs["min_tracking_confidence"], 0.6)
        self.base_options.assert_called_once_with(model_asset_path="bundled-model.task")

    def test_video_timestamps_strictly_increase_with_same_clock_millisecond(self):
        calls = 0

        def read():
            nonlocal calls
            calls += 1
            if calls <= 3:
                return True, "bgr-frame"
            self.worker.stopping.set()
            return False, None

        self.capture.read.side_effect = read
        with patch("pphandcontrol.camera.monotonic", return_value=1.0):
            self.worker.run()
        self.assertEqual([call.args[1] for call in self.landmarker.detect_for_video.call_args_list],
                         [1000, 1001, 1002])

    def test_inference_exception_publishes_error_and_releases_resources(self):
        self.capture.read.return_value = (True, "bgr-frame")
        self.landmarker.detect_for_video.side_effect = RuntimeError("inference failed")
        self.worker.run()
        self.assertEqual(self.events.get_nowait().error, "inference failed")
        self.capture.release.assert_called_once_with()
        self.landmarker.close.assert_called_once_with()

    def test_model_initialization_failure_releases_camera(self):
        self.factory.side_effect = RuntimeError("model unavailable")
        self.worker.run()
        self.assertEqual(self.events.get_nowait().error, "model unavailable")
        self.capture.release.assert_called_once_with()

    def test_stop_joins_worker_and_releases_camera_and_model(self):
        entered_read = Event()

        def read():
            entered_read.set()
            # Simulate a read that completes as shutdown is requested.
            self.worker.stopping.wait = Event.wait.__get__(self.worker.stopping)
            self.worker.stopping.wait(1.0)
            return True, "last-frame"

        self.capture.read.side_effect = read
        self.worker.start()
        self.assertTrue(entered_read.wait(1.0))
        self.assertTrue(self.worker.stop(timeout=1.0))
        self.assertTrue(self.events.empty())
        self.capture.release.assert_called_once_with()
        self.landmarker.close.assert_called_once_with()
        self.assertTrue(self.worker.stop(timeout=1.0))

    def test_capture_is_released_even_if_model_close_raises(self):
        self.stop_after_one_frame()
        self.landmarker.close.side_effect = RuntimeError("close failed")
        try:
            self.worker.run()
        except RuntimeError:
            pass
        self.capture.release.assert_called_once_with()

    def test_latest_frame_queue_replaces_old_frame_with_error(self):
        publish_latest(self.events, CameraEvent(7, 1.0, frame="old-frame"))
        publish_latest(self.events, CameraEvent(7, 2.0, error="camera lost"))
        self.assertEqual(self.events.qsize(), 1)
        event = self.events.get_nowait()
        self.assertEqual(event.error, "camera lost")
        self.assertIsNone(event.frame)


if __name__ == "__main__":
    unittest.main()
