"""Camera-independent, conservative open-palm swipe recognition.

Coordinates are normalized to the *mirrored preview*. Increasing x therefore
means movement toward the preview's right edge. No keyboard or camera access
belongs in this module, which also makes recognition reproducible in tests.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from typing import Literal

Action = Literal["next", "previous"]
Point = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class HandSample:
    timestamp: float
    points: tuple[Point, ...]
    confidence: float = 1.0


class SwipeDetector:
    """Recognize one deliberate swipe after a stationary open-palm hold.

    Call ``update`` once per processed camera frame, including frames with no
    hands. ``reset`` must be called on pause, resume, and configuration changes.
    Tracking interruptions disarm the detector but preserve its cooldown.
    """

    THRESHOLDS = {"Low": 0.26, "Medium": 0.20, "High": 0.14}
    MIN_CONFIDENCE = 0.60
    HOLD_SECONDS = 0.25
    WINDOW_SECONDS = 0.80
    MAX_FRAME_GAP = 0.25
    STABLE_RADIUS = 0.025
    MAX_FRAME_TRAVEL = 0.17
    MAX_SPEED = 3.5

    def __init__(
        self,
        sensitivity: str = "Medium",
        reverse: bool = False,
        cooldown: float = 0.8,
    ) -> None:
        if sensitivity not in self.THRESHOLDS:
            raise ValueError("Sensitivity must be Low, Medium, or High")
        if not isinstance(reverse, bool):
            raise ValueError("Reverse must be a boolean")
        if not math.isfinite(cooldown) or cooldown < 0:
            raise ValueError("Cooldown must be a finite, nonnegative number")
        self.sensitivity = sensitivity
        self.reverse = reverse
        self.cooldown = float(cooldown)
        self.reset()

    def reset(self) -> None:
        self._last_action_at = -math.inf
        self._clear_tracking()
        self.status = "Paused or waiting for an open palm"

    def _clear_tracking(self) -> None:
        self._last_timestamp: float | None = None
        self._last_center: tuple[float, float] | None = None
        self._last_scale: float | None = None
        self._last_chirality: float | None = None
        self._stable_since: float | None = None
        self._stable_anchor: tuple[float, float] | None = None
        self._armed = False
        self._motion: deque[tuple[float, float, float]] = deque()

    def _reject(self, status: str) -> None:
        self._clear_tracking()
        self.status = status

    @staticmethod
    def _distance(a: Point, b: Point) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    @classmethod
    def _joint_angle(cls, a: Point, b: Point, c: Point) -> float:
        first = tuple(x - y for x, y in zip(a, b))
        second = tuple(x - y for x, y in zip(c, b))
        denominator = cls._distance(a, b) * cls._distance(c, b)
        if denominator < 1e-10:
            return 0.0
        cosine = sum(x * y for x, y in zip(first, second)) / denominator
        return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))

    @classmethod
    def _open_palm(cls, points: tuple[Point, ...]) -> bool:
        # Joint angles work when the palm rotates in the image. Comparing the
        # tip's y position to its knuckle would fail for sideways-facing hands.
        for mcp, pip, dip, tip in ((5, 6, 7, 8), (9, 10, 11, 12),
                                   (13, 14, 15, 16), (17, 18, 19, 20)):
            if cls._joint_angle(points[mcp], points[pip], points[dip]) < 155:
                return False
            if cls._joint_angle(points[pip], points[dip], points[tip]) < 145:
                return False
            if cls._distance(points[mcp], points[tip]) < 1.5 * cls._distance(
                points[mcp], points[pip]
            ):
                return False
        return True

    @staticmethod
    def _valid_sample(hand: HandSample, timestamp: float) -> bool:
        try:
            return (
                math.isfinite(hand.timestamp)
                and abs(timestamp - hand.timestamp) <= SwipeDetector.MAX_FRAME_GAP
                and math.isfinite(hand.confidence)
                and len(hand.points) == 21
                and all(len(point) == 3 and all(math.isfinite(v) for v in point)
                        for point in hand.points)
            )
        except (AttributeError, TypeError, ValueError, OverflowError):
            return False

    def update(self, hands: list[HandSample], timestamp: float) -> Action | None:
        try:
            valid_time = math.isfinite(timestamp)
        except (TypeError, ValueError):
            valid_time = False
        if not valid_time:
            self._reject("Invalid camera timestamp")
            return None
        if len(hands) != 1:
            self._reject("Show one open palm" if not hands else "Multiple hands: hold one palm up")
            return None
        hand = hands[0]
        if not self._valid_sample(hand, timestamp):
            self._reject("Tracking interrupted: hold your palm still")
            return None
        if hand.confidence < self.MIN_CONFIDENCE:
            self._reject("Low tracking confidence: improve lighting")
            return None
        if not self._open_palm(hand.points):
            self._reject("Open all four fingers")
            return None

        points = hand.points
        center = (
            sum(points[i][0] for i in (0, 5, 9, 13, 17)) / 5,
            sum(points[i][1] for i in (0, 5, 9, 13, 17)) / 5,
        )
        scale = self._distance(points[5], points[17])
        if scale < 0.015:
            self._reject("Move your palm closer to the camera")
            return None
        # A substantial change in scale or palm orientation can indicate a
        # different hand replacing the tracked hand. Require another hold.
        wrist, index, pinky = points[0], points[5], points[17]
        chirality = ((index[0] - wrist[0]) * (pinky[1] - wrist[1])
                     - (index[1] - wrist[1]) * (pinky[0] - wrist[0])) / scale**2
        if self._last_timestamp is not None:
            elapsed = timestamp - self._last_timestamp
            travel = math.dist(center, self._last_center)  # type: ignore[arg-type]
            scale_ratio = scale / self._last_scale  # type: ignore[operator]
            switched_orientation = (
                abs(chirality) > 0.10
                and abs(self._last_chirality or 0) > 0.10
                and chirality * (self._last_chirality or 0) < 0
            )
            if (elapsed <= 0 or elapsed > self.MAX_FRAME_GAP
                    or travel > self.MAX_FRAME_TRAVEL
                    or (elapsed > 0 and travel / elapsed > self.MAX_SPEED)
                    or not 0.60 <= scale_ratio <= 1.65
                    or switched_orientation):
                self._clear_tracking()

        self._last_timestamp = timestamp
        self._last_center = center
        self._last_scale = scale
        self._last_chirality = chirality

        if not self._armed:
            if (self._stable_anchor is None
                    or math.dist(center, self._stable_anchor) > self.STABLE_RADIUS):
                self._stable_since = timestamp
                self._stable_anchor = center
            cooling_down = timestamp - self._last_action_at < self.cooldown
            if cooling_down:
                self.status = "Cooldown: hold your palm still"
                return None
            if timestamp - self._stable_since < self.HOLD_SECONDS - 1e-9:  # type: ignore[operator]
                self.status = "Hold your open palm still"
                return None
            self._armed = True
            self._motion.clear()
            self._motion.append((timestamp, *center))
            self.status = ("Ready: swipe left for previous, right for next" if self.reverse
                           else "Ready: swipe left for next, right for previous")
            return None

        self._motion.append((timestamp, *center))
        while self._motion and timestamp - self._motion[0][0] > self.WINDOW_SECONDS:
            self._motion.popleft()
        _, origin_x, origin_y = self._motion[0]
        dx, dy = center[0] - origin_x, center[1] - origin_y
        vertical_span = max(p[2] for p in self._motion) - min(p[2] for p in self._motion)
        if vertical_span >= 0.08 and vertical_span >= abs(dx) * 0.6:
            self._armed = False
            self._stable_anchor = center
            self._stable_since = timestamp
            self._motion.clear()
            self.status = "Vertical movement ignored: hold your palm still"
            return None
        threshold = self.THRESHOLDS[self.sensitivity]
        if abs(dx) + 1e-9 < threshold or abs(dx) <= 2 * abs(dy):
            self.status = "Ready: swipe horizontally"
            return None
        if vertical_span * 2 >= abs(dx):
            return None
        total_horizontal = sum(abs(b[1] - a[1]) for a, b in zip(self._motion, list(self._motion)[1:]))
        if total_horizontal and abs(dx) / total_horizontal < 0.75:
            self._armed = False
            self._stable_anchor = center
            self._stable_since = timestamp
            self._motion.clear()
            self.status = "Changing direction ignored: hold your palm still"
            return None
        action: Action = "next" if dx < 0 else "previous"
        if self.reverse:
            action = "previous" if action == "next" else "next"
        self._last_action_at = timestamp
        self._armed = False
        self._stable_anchor = center
        self._stable_since = timestamp
        self._motion.clear()
        self.status = "Next" if action == "next" else "Previous"
        return action
