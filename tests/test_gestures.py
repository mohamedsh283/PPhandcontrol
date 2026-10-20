"""Behavioral checks using synthetic landmark sequences, without a webcam."""

from dataclasses import replace
import math
import unittest

from pphandcontrol.gestures import HandSample, SwipeDetector


def palm(timestamp, x=0.0, y=0.0, *, confidence=1.0, rotation=0.0, mirror=False):
    points = [(0.5, 0.7, 0.0)] * 21
    points[1:5] = [(0.45, 0.64, 0.0), (0.40, 0.60, 0.0),
                   (0.36, 0.57, 0.0), (0.32, 0.54, 0.0)]
    for start, finger_x in ((5, 0.42), (9, 0.48), (13, 0.54), (17, 0.60)):
        for offset, finger_y in enumerate((0.55, 0.45, 0.37, 0.30)):
            points[start + offset] = (finger_x, finger_y, 0.0)
    transformed = []
    for px, py, pz in points:
        if mirror:
            px = 1 - px
        px, py = px - 0.5, py - 0.5
        transformed.append((
            0.5 + px * math.cos(rotation) - py * math.sin(rotation) + x,
            0.5 + px * math.sin(rotation) + py * math.cos(rotation) + y,
            pz,
        ))
    return HandSample(timestamp, tuple(transformed), confidence)


def arm(detector, start=0.0, x=0.0, **kwargs):
    for offset in (0.0, 0.1, 0.2, 0.3):
        timestamp = start + offset
        assert detector.update([palm(timestamp, x, **kwargs)], timestamp) is None
    return start + 0.3


def swipe(detector, start=0.3, direction=-1, distance=0.25, x=0.0, **kwargs):
    actions = []
    steps = math.ceil(distance / 0.05)
    for step in range(1, steps + 1):
        timestamp = start + 0.05 * step
        result = detector.update([
            palm(timestamp, x + direction * min(step * 0.05, distance), **kwargs)
        ], timestamp)
        if result:
            actions.append(result)
    return actions


class SwipeDetectorTests(unittest.TestCase):
    def test_mirrored_left_is_next_and_right_is_previous(self):
        for direction, expected in ((-1, "next"), (1, "previous")):
            with self.subTest(direction=direction):
                detector = SwipeDetector()
                arm(detector)
                self.assertEqual(swipe(detector, direction=direction), [expected])

    def test_reverse_swaps_both_directions(self):
        for direction, expected in ((-1, "previous"), (1, "next")):
            with self.subTest(direction=direction):
                detector = SwipeDetector(reverse=True)
                arm(detector)
                self.assertEqual(swipe(detector, direction=direction), [expected])

    def test_requires_stable_hold_before_first_swipe(self):
        detector = SwipeDetector()
        self.assertEqual(swipe(detector, start=0.0), [])

    def test_sensitivity_changes_minimum_travel(self):
        for sensitivity, distance, expected in (
            ("High", 0.15, ["next"]),
            ("Medium", 0.15, []),
            ("Medium", 0.20, ["next"]),
            ("Low", 0.25, []),
            ("Low", 0.30, ["next"]),
        ):
            with self.subTest(sensitivity=sensitivity, distance=distance):
                detector = SwipeDetector(sensitivity)
                arm(detector)
                self.assertEqual(swipe(detector, distance=distance), expected)

    def test_continuous_movement_emits_only_one_command(self):
        detector = SwipeDetector()
        arm(detector)
        self.assertEqual(swipe(detector, distance=0.60), ["next"])

    def test_rearms_after_cooldown_and_stationary_hold(self):
        detector = SwipeDetector()
        arm(detector)
        self.assertEqual(swipe(detector), ["next"])
        for index in range(6, 24):
            timestamp = 0.3 + index * 0.05
            self.assertIsNone(detector.update([palm(timestamp, -0.25)], timestamp))
        self.assertEqual(swipe(detector, start=1.45, x=-0.25, direction=1), ["previous"])

    def test_cooldown_survives_temporary_tracking_loss(self):
        detector = SwipeDetector()
        arm(detector)
        self.assertEqual(swipe(detector), ["next"])
        self.assertIsNone(detector.update([], 0.56))
        arm(detector, start=0.6, x=-0.25)
        self.assertEqual(swipe(detector, start=0.9, x=-0.25, direction=1), [])

    def test_reset_clears_movement_on_pause_or_settings_change(self):
        detector = SwipeDetector()
        arm(detector)
        self.assertEqual(swipe(detector, distance=0.1), [])
        detector.reset()
        self.assertEqual(swipe(detector, start=0.4, x=-0.1, distance=0.3), [])

    def test_stationary_jitter_does_not_navigate(self):
        detector = SwipeDetector()
        for index in range(100):
            timestamp = index * 0.04
            self.assertIsNone(detector.update([
                palm(timestamp, x=math.sin(index) * 0.006, y=math.cos(index) * 0.006)
            ], timestamp))

    def test_vertical_and_diagonal_motion_do_not_navigate(self):
        for ratio in (1.0, 3.0):
            with self.subTest(vertical_ratio=ratio):
                detector = SwipeDetector()
                arm(detector)
                for index in range(1, 9):
                    timestamp = 0.3 + index * 0.05
                    self.assertIsNone(detector.update([
                        palm(timestamp, x=-index * 0.03, y=index * 0.03 * ratio)
                    ], timestamp))

    def test_slow_drift_beyond_motion_window_does_not_navigate(self):
        detector = SwipeDetector()
        arm(detector)
        for index in range(1, 31):
            timestamp = 0.3 + index * 0.1
            self.assertIsNone(detector.update([palm(timestamp, -index * 0.01)], timestamp))

    def test_closed_finger_disarms(self):
        detector = SwipeDetector()
        arm(detector)
        sample = palm(0.35)
        points = list(sample.points)
        points[11] = (0.48, 0.50, 0.0)
        points[12] = (0.48, 0.54, 0.0)
        self.assertIsNone(detector.update([replace(sample, points=tuple(points))], 0.35))
        self.assertEqual(swipe(detector, start=0.35), [])

    def test_open_palm_rotation_preserves_recognition(self):
        detector = SwipeDetector()
        arm(detector, rotation=math.pi / 2)
        self.assertEqual(swipe(detector, rotation=math.pi / 2), ["next"])

    def test_low_confidence_disarms(self):
        detector = SwipeDetector()
        arm(detector)
        self.assertIsNone(detector.update([palm(0.35, confidence=0.59)], 0.35))
        self.assertEqual(swipe(detector, start=0.35), [])

    def test_zero_and_multiple_hands_disarm(self):
        for hands in ([], [palm(0.35), palm(0.35, x=0.2)]):
            with self.subTest(hands=len(hands)):
                detector = SwipeDetector()
                arm(detector)
                self.assertIsNone(detector.update(hands, 0.35))
                self.assertEqual(swipe(detector, start=0.35), [])

    def test_frame_gap_discards_previous_movement(self):
        detector = SwipeDetector()
        arm(detector)
        self.assertEqual(swipe(detector, distance=0.1), [])
        self.assertIsNone(detector.update([palm(0.8, -0.2)], 0.8))
        self.assertEqual(swipe(detector, start=0.8, x=-0.2), [])

    def test_position_jump_cannot_complete_swipe(self):
        detector = SwipeDetector()
        arm(detector)
        self.assertIsNone(detector.update([palm(0.35, -0.4)], 0.35))
        self.assertEqual(swipe(detector, start=0.35, x=-0.4), [])

    def test_replacement_hand_requires_new_hold(self):
        detector = SwipeDetector()
        arm(detector)
        self.assertIsNone(detector.update([palm(0.35, mirror=True)], 0.35))
        self.assertEqual(swipe(detector, start=0.35, mirror=True), [])

    def test_nonmonotonic_time_discards_history(self):
        detector = SwipeDetector()
        arm(detector)
        self.assertIsNone(detector.update([palm(0.25, -0.05)], 0.25))
        self.assertEqual(swipe(detector, start=0.25, x=-0.05), [])

    def test_malformed_samples_are_ignored(self):
        invalid = [
            HandSample(0.0, ()),
            replace(palm(0.0), points=((math.nan, 0.0, 0.0),) * 21),
            replace(palm(0.0), confidence=math.nan),
            palm(-1.0),
        ]
        for sample in invalid:
            with self.subTest(sample=sample):
                detector = SwipeDetector()
                self.assertIsNone(detector.update([sample], 0.0))
        self.assertIsNone(SwipeDetector().update([], math.nan))

    def test_invalid_configuration_is_rejected(self):
        for kwargs in ({"sensitivity": "Ultra"}, {"reverse": "yes"},
                       {"cooldown": -1.0}, {"cooldown": math.inf}):
            with self.subTest(kwargs=kwargs):
                self.assertRaises(ValueError, SwipeDetector, **kwargs)


if __name__ == "__main__":
    unittest.main()
