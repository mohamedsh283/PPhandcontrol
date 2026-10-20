"""Offline gesture decisions, independent of cameras, Tk and Windows input."""
from collections import deque
from dataclasses import dataclass
import math

MODES = ("Thumbs", "Point & swipe")


@dataclass(frozen=True, slots=True)
class HandSample:
    timestamp: float
    points: tuple[tuple[float, float, float], ...]
    confidence: float = 1.0
    gesture: str | None = None
    gesture_score: float = 0.0


def valid_sample(hand: HandSample, timestamp: float) -> bool:
    try:
        return (math.isfinite(hand.timestamp) and abs(timestamp - hand.timestamp) <= 0.5
                and math.isfinite(hand.confidence) and hand.confidence >= 0.6
                and math.isfinite(hand.gesture_score) and len(hand.points) == 21
                and all(len(p) == 3 and all(math.isfinite(v) for v in p) for p in hand.points))
    except (TypeError, ValueError, AttributeError):
        return False


def valid_time(timestamp) -> bool:
    try:
        return math.isfinite(timestamp)
    except (TypeError, ValueError):
        return False


class ThumbDetector:
    """One command per held pose; relax briefly to repeat the same direction.

    Short recognition flicker cannot unlock a held thumb. A stable opposite
    thumb may fire directly after cooldown; no hand-position hold is required.
    """
    HOLD_SECONDS = {"High": 0.20, "Medium": 0.35, "Low": 0.55}
    MIN_SCORE = 0.60
    RELEASE_SECONDS = 0.25
    ACTIONS = {"Thumb_Up": "next", "Thumb_Down": "previous"}
    NEUTRAL = {"Closed_Fist", "Open_Palm", "Pointing_Up", "Victory", "ILoveYou"}

    def __init__(self, sensitivity="Medium", cooldown=0.8):
        if sensitivity not in self.HOLD_SECONDS or not valid_time(cooldown) or cooldown < 0:
            raise ValueError("Use Low, Medium or High sensitivity and a nonnegative cooldown")
        self.sensitivity = sensitivity
        self.cooldown = cooldown
        self.reset()

    def reset(self):
        self._last_action = -math.inf
        self._last_time = None
        self._latched = None
        self._clear_candidate()
        self._release_since = None
        self._release_frames = 0
        self.status = "Ready: thumbs up for Next, thumbs down for Previous"

    def _clear_candidate(self):
        self._candidate = None
        self._candidate_since = None
        self._candidate_frames = 0
        self._last_good = -math.inf

    def _release(self, timestamp):
        self._clear_candidate()
        if self._release_since is None:
            self._release_since = timestamp
            self._release_frames = 0
        self._release_frames += 1
        if timestamp - self._release_since >= self.RELEASE_SECONDS - 1e-9 and self._release_frames >= 2:
            self._latched = None
            self.status = "Ready: show a thumbs up or thumbs down"
        else:
            self.status = "Relax your thumb briefly before repeating"

    def update(self, hands, timestamp):
        if not valid_time(timestamp):
            self._clear_candidate()
            self._release_since = None
            return None
        if self._last_time is not None and not 0 < timestamp - self._last_time <= 0.5:
            self._clear_candidate()
            self._release_since = None
        self._last_time = timestamp
        if not hands:
            self._release(timestamp)
            return None
        if len(hands) != 1 or not valid_sample(hands[0], timestamp):
            self._clear_candidate()
            self._release_since = None
            self.status = "Show one hand clearly; improve lighting if tracking is uncertain"
            return None
        hand = hands[0]
        pose = hand.gesture if hand.gesture_score >= self.MIN_SCORE else None
        if pose in self.NEUTRAL:
            self._release(timestamp)
            return None
        self._release_since = None
        if pose not in self.ACTIONS:
            # Tolerate a single uncertain frame during a deliberate hold.
            if timestamp - self._last_good > 0.12:
                self._clear_candidate()
            self.status = "Show a clear thumbs up or thumbs down"
            return None
        if pose == self._latched:
            self._clear_candidate()
            self.status = "Command sent — relax your thumb before repeating"
            return None
        if pose != self._candidate:
            self._candidate = pose
            self._candidate_since = timestamp
            self._candidate_frames = 0
        self._candidate_frames += 1
        self._last_good = timestamp
        name = "Thumbs up" if pose == "Thumb_Up" else "Thumbs down"
        self.status = f"{name} detected — hold briefly"
        if (timestamp - self._candidate_since >= self.HOLD_SECONDS[self.sensitivity] - 1e-9
                and self._candidate_frames >= 2
                and timestamp - self._last_action >= self.cooldown - 1e-9):
            self._latched = pose
            self._last_action = timestamp
            self._clear_candidate()
            self.status = f"{name}: {self.ACTIONS[pose].upper()} sent — relax to repeat"
            return self.ACTIONS[pose]
        return None


def joint_angle(a, b, c):
    u = tuple(x - y for x, y in zip(a, b))
    v = tuple(x - y for x, y in zip(c, b))
    length = math.sqrt(sum(x * x for x in u) * sum(x * x for x in v))
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(u, v)) / length)))) if length > 1e-10 else 0.0


def pointing(hand):
    """Index extended, other fingers folded, including pointing into the lens.

    Use 3D joint geometry so pointing toward the camera is supported, rather
    than depending solely on the recognizer's upright Pointing_Up category.
    """
    if hand.gesture_score >= 0.65:
        if hand.gesture == "Pointing_Up":
            return True
        if hand.gesture in ("Open_Palm", "Thumb_Up", "Thumb_Down", "Closed_Fist", "Victory", "ILoveYou"):
            return False
    p = hand.points
    extended = (joint_angle(p[5], p[6], p[7]) >= 150
                and joint_angle(p[6], p[7], p[8]) >= 145
                and math.dist(p[5], p[8]) >= 1.7 * math.dist(p[5], p[6])
                and math.dist(p[5], p[8]) > 0.015)
    folded = sum(joint_angle(p[m], p[m + 1], p[m + 2]) < 145
                 or math.dist(p[0], p[m + 3]) < math.dist(p[0], p[m + 1])
                 for m in (9, 13, 17))
    return extended and folded == 3


class PointSwipeDetector:
    """Point with one index finger and move the hand left/right; no palm hold."""
    THRESHOLDS = {"High": 0.10, "Medium": 0.14, "Low": 0.20}

    def __init__(self, sensitivity="Medium", cooldown=0.8):
        if sensitivity not in self.THRESHOLDS or not valid_time(cooldown) or cooldown < 0:
            raise ValueError("Use Low, Medium or High sensitivity and a nonnegative cooldown")
        self.sensitivity, self.cooldown = sensitivity, cooldown
        self.reset()

    def reset(self):
        self._last_action = -math.inf
        self._last_time = None
        self._locked = False
        self._release_since = None
        self._motion = deque()
        self.status = "Point your index finger at the camera, then swipe left or right"

    def update(self, hands, timestamp):
        if not valid_time(timestamp):
            self._motion.clear()
            self._release_since = None
            return None
        if self._last_time is not None and not 0 < timestamp - self._last_time <= 0.5:
            self._motion.clear()
            self._release_since = None
        self._last_time = timestamp
        if len(hands) > 1 or (hands and not valid_sample(hands[0], timestamp)):
            self._motion.clear()
            self._release_since = None
            self.status = "Show one pointing hand clearly"
            return None
        if not hands or not pointing(hands[0]):
            self._motion.clear()
            if self._release_since is None:
                self._release_since = timestamp
            if timestamp - self._release_since >= 0.25 - 1e-9:
                self._locked = False
            self.status = "Point your index finger, then swipe; relax it after each command"
            return None
        self._release_since = None
        if self._locked:
            self.status = "Command sent — relax your index finger before another swipe"
            return None
        if timestamp - self._last_action < self.cooldown:
            self._motion.clear()
            self.status = "Cooldown — relax your index finger"
            return None
        p = hands[0].points
        x = sum(p[i][0] for i in (0, 5, 9, 13, 17)) / 5
        y = sum(p[i][1] for i in (0, 5, 9, 13, 17)) / 5
        if self._motion and math.dist((x, y), self._motion[-1][1:]) > 0.18:
            self._motion.clear()
        self._motion.append((timestamp, x, y))
        while len(self._motion) > 1 and timestamp - self._motion[0][0] > 0.9:
            self._motion.popleft()
        t0, x0, y0 = self._motion[0]
        dx, dy = x - x0, y - y0
        vertical = max(item[2] for item in self._motion) - min(item[2] for item in self._motion)
        self.status = "Pointing detected — left for Next, right for Previous"
        if (len(self._motion) < 3 or timestamp - t0 < 0.12 - 1e-9
                or abs(dx) < self.THRESHOLDS[self.sensitivity] - 1e-9
                or abs(dx) <= 2 * abs(dy) or vertical * 2 >= abs(dx)):
            return None
        horizontal = sum(abs(b[1] - a[1]) for a, b in zip(self._motion, list(self._motion)[1:]))
        if horizontal and abs(dx) / horizontal < 0.75:
            self._motion.clear()
            return None
        action = "next" if dx < 0 else "previous"
        self._last_action = timestamp
        self._locked = True
        self._motion.clear()
        self.status = action.upper() + " sent — relax your index finger"
        return action


def create_detector(mode="Thumbs", sensitivity="Medium"):
    if mode == MODES[0]:
        return ThumbDetector(sensitivity)
    if mode == MODES[1]:
        return PointSwipeDetector(sensitivity)
    raise ValueError("Unknown gesture mode")
