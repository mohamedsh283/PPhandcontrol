"""One camera worker; latest-frame delivery prevents queued, delayed gestures."""
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import monotonic
from typing import Any

from .gestures import HandSample


@dataclass(frozen=True)
class CameraEvent:
    generation: int
    timestamp: float
    frame: Any = None  # RGB uint8 array; never recorded or logged
    hands: tuple[HandSample, ...] = ()
    error: str | None = None


def publish_latest(events: Queue, event: CameraEvent) -> None:
    try:
        events.put_nowait(event)
    except Full:
        try:
            events.get_nowait()
        except Empty:
            pass
        try:
            events.put_nowait(event)
        except Full:
            pass


class TrackingWorker(Thread):
    def __init__(self, camera_index: int, generation: int, model_path: Path, events: Queue):
        super().__init__(name="PPhandcontrol camera", daemon=True)
        self.camera_index = camera_index
        self.generation = generation
        self.model_path = model_path
        self.events = events
        self.stopping = Event()

    def stop(self, timeout: float = 3.0) -> bool:
        self.stopping.set()
        if self.is_alive():
            self.join(timeout)
        return not self.is_alive()

    def run(self) -> None:
        capture = None
        landmarker = None
        try:
            import cv2
            import mediapipe as mp

            capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not capture.isOpened():
                capture.release()
                capture = cv2.VideoCapture(self.camera_index, cv2.CAP_MSMF)
            if not capture.isOpened():
                raise RuntimeError("Camera could not open. Check Windows camera permissions, close other camera apps, or select another camera index.")
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            capture.set(cv2.CAP_PROP_FPS, 30)
            options = mp.tasks.vision.GestureRecognizerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(self.model_path)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                canned_gestures_classifier_options=mp.tasks.components.processors.ClassifierOptions(score_threshold=0.5),
            )
            landmarker = mp.tasks.vision.GestureRecognizer.create_from_options(options)
            last_ms = -1
            failures = 0
            while not self.stopping.is_set():
                ok, frame = capture.read()
                captured_at = monotonic()
                if self.stopping.is_set():
                    break
                if not ok or frame is None:
                    failures += 1
                    if failures >= 5:
                        raise RuntimeError("Camera stopped delivering images. Navigation is paused. Reconnect the camera, then click Retry camera.")
                    self.stopping.wait(0.05)
                    continue
                failures = 0
                rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
                stamp = max(last_ms + 1, int(captured_at * 1000))
                last_ms = stamp
                result = landmarker.recognize_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), stamp)
                # Tasks exposes handedness confidence, not per-hand tracking confidence.
                # Detection, presence and tracking are gated by the options above.
                hands = tuple(HandSample(
                    timestamp=captured_at,
                    points=tuple((p.x, p.y, p.z) for p in landmarks),
                    confidence=1.0,
                    gesture=result.gestures[i][0].category_name if i < len(result.gestures) and result.gestures[i] else None,
                    gesture_score=result.gestures[i][0].score if i < len(result.gestures) and result.gestures[i] else 0.0,
                ) for i, landmarks in enumerate(result.hand_landmarks))
                publish_latest(self.events, CameraEvent(self.generation, captured_at, rgb, hands))
        except Exception as exc:
            if not self.stopping.is_set():
                publish_latest(self.events, CameraEvent(self.generation, monotonic(), error=str(exc)))
        finally:
            cleanup_errors = []
            for resource, method in ((landmarker, "close"), (capture, "release")):
                if resource is not None:
                    try:
                        getattr(resource, method)()
                    except Exception as exc:
                        cleanup_errors.append(str(exc))
            if cleanup_errors and not self.stopping.is_set():
                publish_latest(self.events, CameraEvent(
                    self.generation, monotonic(), error="Camera cleanup failed: " + "; ".join(cleanup_errors)))
