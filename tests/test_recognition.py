"""Use the installed SDK and bundled model to catch runtime API mismatches."""
from queue import Queue
import unittest
from unittest.mock import Mock, patch

import mediapipe as mp
import numpy as np

from pphandcontrol.camera import TrackingWorker
from pphandcontrol.paths import model_path
from pphandcontrol.recognition import recognizer_options


class RecognitionIntegrationTests(unittest.TestCase):
    def test_options_use_actual_installed_sdk(self):
        options = recognizer_options(model_path())
        self.assertIsInstance(options, mp.tasks.vision.GestureRecognizerOptions)
        self.assertEqual(options.running_mode, mp.tasks.vision.RunningMode.VIDEO)
        self.assertEqual(options.num_hands, 2)
        self.assertEqual(options.canned_gesture_classifier_options.score_threshold, 0.5)
        self.assertEqual(options.min_hand_detection_confidence, 0.5)
        self.assertEqual(options.min_hand_presence_confidence, 0.5)
        self.assertEqual(options.min_tracking_confidence, 0.5)

    def test_camera_worker_initializes_real_model_and_processes_video(self):
        # Only replace hardware capture; options, SDK, model and inference are real.
        events = Queue(maxsize=1)
        worker = TrackingWorker(0, 1, model_path(), events)
        capture = Mock()
        capture.isOpened.return_value = True
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        reads = 0

        def read():
            nonlocal reads
            reads += 1
            if reads == 1:
                return True, frame
            worker.stopping.set()
            return False, None

        capture.read.side_effect = read
        with patch("cv2.VideoCapture", return_value=capture):
            worker.run()
        event = events.get_nowait()
        self.assertIsNone(event.error, event.error)
        self.assertEqual(event.frame.shape, (480, 640, 3))
        self.assertEqual(event.hands, ())
        capture.release.assert_called_once_with()
