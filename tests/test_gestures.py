"""Gesture behavior at realistic cadences, without cameras or native input."""
from dataclasses import replace
import math
import unittest

from pphandcontrol.gestures import HandSample, ThumbDetector, PointSwipeDetector, create_detector, pointing


def sample(t, pose="Thumb_Up", score=0.95, dx=0, dy=0, toward_camera=False, mirror=False):
    p = [(0.5, 0.75, 0.0)] * 21
    p[1:5] = [(0.45, .67, 0), (.40, .61, 0), (.36, .54, 0), (.34, .46, 0)]
    for m, x in ((5, .42), (9, .48), (13, .54), (17, .60)):
        p[m:m+4] = [(x, .59, 0), (x, .49, -.01), (x, .55, -.04), (x, .66, -.04)]
    if pose in ("Pointing_Up", "geometry"):
        p[5:9] = [(.42, .59, 0), (.42, .47, -.01), (.42, .36, -.02), (.42, .25, -.03)]
        if toward_camera:
            p[5:9] = [(.42, .59, 0), (.42, .58, -.12), (.42, .57, -.23), (.42, .56, -.34)]
    if pose == "Open_Palm":
        for m, x in ((5,.42),(9,.48),(13,.54),(17,.60)):
            p[m:m+4] = [(x, .59, 0),(x,.47,0),(x,.36,0),(x,.25,0)]
    pts = tuple(((1-x if mirror else x)+dx, y+dy, z) for x,y,z in p)
    return HandSample(t, pts, 1.0, None if pose == "geometry" else pose, score)


def hold(detector, pose="Thumb_Up", start=0.0, duration=1.0, step=.05, **kwargs):
    actions = []
    for i in range(round(duration / step) + 1):
        t = round(start + i * step, 6)
        action = detector.update([sample(t, pose, **kwargs)], t)
        if action:
            actions.append(action)
    return actions


def swipe(detector, direction=-1, start=0.0, distance=.22, pose="Pointing_Up", **kwargs):
    actions = []
    for i in range(7):
        t = round(start + i*.05, 6)
        action = detector.update([sample(t, pose, dx=direction*distance*i/6, **kwargs)], t)
        if action:
            actions.append(action)
    return actions


class ThumbTests(unittest.TestCase):
    def test_up_next_down_previous(self):
        self.assertEqual(hold(ThumbDetector()), ["next"])
        self.assertEqual(hold(ThumbDetector(), "Thumb_Down"), ["previous"])

    def test_long_hold_never_repeats(self):
        self.assertEqual(hold(ThumbDetector(), duration=6), ["next"])

    def test_no_swipe_or_position_hold_needed(self):
        d = ThumbDetector()
        actions = []
        for i in range(15):
            t = i*.05
            action = d.update([sample(t, dx=.06*math.sin(i))], t)
            if action: actions.append(action)
        self.assertEqual(actions, ["next"])

    def test_confident_neutral_rearms_same_pose(self):
        d = ThumbDetector()
        self.assertEqual(hold(d), ["next"])
        self.assertEqual(hold(d, "Closed_Fist", start=1.05, duration=.3), [])
        self.assertEqual(hold(d, start=1.4), ["next"])

    def test_hand_lowered_rearms(self):
        d = ThumbDetector()
        hold(d)
        for i in range(7): d.update([], 1.05+i*.05)
        self.assertEqual(hold(d, start=1.4), ["next"])

    def test_brief_hand_loss_does_not_repeat(self):
        d = ThumbDetector()
        hold(d)
        d.update([], 1.05)
        d.update([], 1.1)
        self.assertEqual(hold(d, start=1.15), [])

    def test_uncertain_pose_does_not_unlock_held_thumb(self):
        d = ThumbDetector()
        hold(d)
        hold(d, "None", start=1.05, duration=.6)
        self.assertEqual(hold(d, start=1.7), [])

    def test_opposite_pose_can_fire_after_cooldown(self):
        d = ThumbDetector()
        self.assertEqual(hold(d, duration=.4), ["next"])
        self.assertEqual(hold(d, "Thumb_Down", start=.45, duration=1), ["previous"])

    def test_low_score_never_emits(self):
        self.assertEqual(hold(ThumbDetector(), score=.59), [])

    def test_short_candidate_flicker_is_tolerated(self):
        d = ThumbDetector()
        for t in (0,.05,.1,.15,.2,.25): self.assertIsNone(d.update([sample(t)], t))
        self.assertIsNone(d.update([sample(.30, "None", .2)], .30))
        self.assertEqual(d.update([sample(.35)], .35), "next")

    def test_hold_time_depends_on_sensitivity(self):
        for setting, expected in (("High", ["next"]), ("Medium", []), ("Low", [])):
            self.assertEqual(hold(ThumbDetector(setting), duration=.25), expected)

    def test_one_frame_cannot_fire(self):
        d = ThumbDetector()
        self.assertIsNone(d.update([sample(0)], 0))
        self.assertIsNone(d.update([sample(1)], 1))

    def test_lower_frame_rate_still_recognizes_a_held_thumb(self):
        d = ThumbDetector()
        self.assertIsNone(d.update([sample(0)], 0))
        self.assertEqual(d.update([sample(.4)], .4), "next")

    def test_pointing_is_neutral_in_thumbs_mode(self):
        self.assertEqual(hold(ThumbDetector(), "Pointing_Up", duration=2), [])

    def test_frame_gap_and_nonmonotonic_time_restart_hold(self):
        for next_time in (.2, 1.0):
            d = ThumbDetector()
            hold(d, duration=.25)
            self.assertIsNone(d.update([sample(next_time)], next_time))

    def test_multiple_hands_and_invalid_input_never_emit(self):
        d = ThumbDetector()
        for i in range(20):
            t=i*.05
            self.assertIsNone(d.update([sample(t), sample(t)], t))
        for bad in (replace(sample(2), confidence=.3), replace(sample(2), gesture_score=math.nan),
                    replace(sample(2), points=((math.nan,0,0),)*21)):
            self.assertIsNone(d.update([bad], 2))
        self.assertIsNone(d.update([], math.nan))

    def test_pause_reset_requires_a_fresh_hold(self):
        d=ThumbDetector()
        hold(d, duration=.25)
        d.reset()
        self.assertIsNone(d.update([sample(.3)], .3))
        self.assertIsNone(d.update([sample(.4)], .4))


class PointSwipeTests(unittest.TestCase):
    def test_left_next_right_previous(self):
        for direction, expected in ((-1,"next"),(1,"previous")):
            self.assertEqual(swipe(PointSwipeDetector(), direction), [expected])

    def test_geometry_supports_index_pointing_into_camera_and_both_hands(self):
        for mirror in (False,True):
            self.assertTrue(pointing(sample(0,"geometry", toward_camera=True, mirror=mirror)))
            self.assertEqual(swipe(PointSwipeDetector(), pose="geometry", toward_camera=True, mirror=mirror), ["next"])

    def test_open_palm_and_thumbs_do_not_swipe(self):
        for pose in ("Open_Palm","Thumb_Up","Thumb_Down","Closed_Fist"):
            self.assertEqual(swipe(PointSwipeDetector(), pose=pose), [])

    def test_uncategorized_open_hand_cannot_pass_pointing_geometry(self):
        hand = replace(sample(0,"Open_Palm"), gesture=None, gesture_score=0)
        self.assertFalse(pointing(hand))

    def test_confident_other_pose_cannot_pass_index_geometry(self):
        for pose in ("Victory", "ILoveYou", "Open_Palm"):
            hand = replace(sample(0,"Pointing_Up"), gesture=pose)
            self.assertFalse(pointing(hand))

    def test_stationary_point_does_not_fire(self):
        self.assertEqual(hold(PointSwipeDetector(), "Pointing_Up", duration=3), [])

    def test_vertical_and_diagonal_motion_rejected(self):
        for dx in (0,-.03):
            d=PointSwipeDetector()
            for i in range(8):
                t=i*.05
                self.assertIsNone(d.update([sample(t,"Pointing_Up",dx=dx*i,dy=.04*i)], t))

    def test_held_point_and_return_path_cannot_duplicate(self):
        d=PointSwipeDetector()
        self.assertEqual(swipe(d), ["next"])
        self.assertEqual(swipe(d, direction=1, start=.4), [])
        self.assertEqual(hold(d,"Pointing_Up", start=.8, duration=2), [])

    def test_relax_then_new_swipe_rearms(self):
        d=PointSwipeDetector()
        swipe(d)
        hold(d,"Closed_Fist", start=.35,duration=.3)
        self.assertEqual(swipe(d, direction=1,start=1.2), ["previous"])

    def test_sensitivity_changes_travel(self):
        self.assertEqual(swipe(PointSwipeDetector("High"),distance=.12),["next"])
        self.assertEqual(swipe(PointSwipeDetector("Medium"),distance=.12),[])
        self.assertEqual(swipe(PointSwipeDetector("Low"),distance=.17),[])

    def test_jump_and_tracking_gap_do_not_complete_stale_swipe(self):
        d=PointSwipeDetector()
        for t,x in ((0,0),(.1,-.06),(.2,-.5),(1,-.6)):
            self.assertIsNone(d.update([sample(t,"Pointing_Up",dx=x)],t))

    def test_invalid_and_ambiguous_samples_rejected(self):
        d=PointSwipeDetector()
        for i in range(8):
            t=i*.05
            self.assertIsNone(d.update([sample(t,"Pointing_Up"),sample(t,"Pointing_Up")],t))
        self.assertIsNone(d.update([replace(sample(2), points=())],2))
        self.assertIsNone(d.update([],math.nan))


class ModeTests(unittest.TestCase):
    def test_default_and_explicit_mode_selection(self):
        self.assertIsInstance(create_detector(), ThumbDetector)
        self.assertIsInstance(create_detector("Point & swipe"), PointSwipeDetector)
        with self.assertRaises(ValueError): create_detector("Palm")

    def test_invalid_options_rejected(self):
        for cls in (ThumbDetector,PointSwipeDetector):
            for options in ({"sensitivity":"Ultra"},{"cooldown":-1},{"cooldown":math.nan}):
                with self.assertRaises(ValueError): cls(**options)


if __name__ == "__main__":
    unittest.main()
