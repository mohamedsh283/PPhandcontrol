"""Control lifecycle independent of cameras, GUI and Windows APIs."""
from time import monotonic

from .gestures import ThumbDetector, PointSwipeDetector


class ControlSession:
    def __init__(self, detector: ThumbDetector | PointSwipeDetector):
        self.detector = detector
        self.paused = True
        self.ready = False
        self.generation = 0
        self.last_frame_time: float | None = None
        self.error = ""

    def restart_camera(self) -> None:
        self.generation += 1
        self.ready = False
        self.last_frame_time = None
        self.error = ""
        self.pause()

    def pause(self) -> None:
        self.paused = True
        self.detector.reset()

    def toggle(self) -> bool:
        if not self.ready or self.error:
            self.pause()
            return False
        self.paused = not self.paused
        self.detector.reset()
        return True

    def camera_error(self, text: str) -> None:
        self.ready = False
        self.error = text
        self.pause()

    def process(self, event, now: float | None = None) -> str | None:
        if event.generation != self.generation:
            return None
        if event.error:
            self.camera_error(event.error)
            return None
        now = monotonic() if now is None else now
        if now - event.timestamp > 0.25 or event.timestamp > now + 0.01:
            self.detector.reset()
            return None
        self.last_frame_time = event.timestamp
        self.ready = True
        self.error = ""
        if self.paused:
            self.detector.reset()
            return None
        return self.detector.update(list(event.hands), event.timestamp)

    def check_stale(self, now: float | None = None) -> None:
        now = monotonic() if now is None else now
        if self.ready and self.last_frame_time is not None and now - self.last_frame_time > 1.0:
            self.camera_error("Camera images are delayed. Navigation is paused. Click Retry camera.")
