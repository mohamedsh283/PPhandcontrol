"""These tests never load user32 or send real keystrokes."""

import ctypes
import os
import queue
import threading
import time
import unittest

from pphandcontrol import windows as win


class FakeAPI:
    def __init__(self):
        self.foreground = 1234
        self.foreground_pid = os.getpid() + 1
        self.keys_down = set()
        self.sent = []
        self.send_results = []
        self.conflicting_keys = set()
        self.registration_error = 1409
        self.error = 5
        self.registrations = []
        self.unregistrations = []
        self.messages = queue.Queue()
        self.last_message = None
        self.registration_thread = None

    def GetForegroundWindow(self):
        return self.foreground

    def GetWindowThreadProcessId(self, hwnd, pid):
        pid._obj.value = self.foreground_pid
        return 42 if self.foreground_pid else 0

    def GetAsyncKeyState(self, key):
        return 0x8000 if key in self.keys_down else 0

    def SendInput(self, count, events, size):
        self.sent.append(
            ([(event.ki.wVk, event.ki.dwFlags) for event in events], size)
        )
        return self.send_results.pop(0) if self.send_results else count

    def last_error(self):
        return self.error

    def RegisterHotKey(self, hwnd, identifier, modifiers, key):
        self.registration_thread = threading.get_ident()
        self.registrations.append((hwnd, identifier, modifiers, key))
        if key in self.conflicting_keys:
            self.error = self.registration_error
        return key not in self.conflicting_keys

    def UnregisterHotKey(self, hwnd, identifier):
        self.unregistrations.append((hwnd, identifier, threading.get_ident()))
        return True

    def PeekMessageW(self, pointer, hwnd, low, high, remove):
        if remove == win.PM_NOREMOVE:
            return False
        try:
            identifier = self.messages.get_nowait()
        except queue.Empty:
            return False
        pointer._obj.message = win.WM_HOTKEY
        pointer._obj.wParam = identifier
        return True


class ProfileTests(unittest.TestCase):
    def test_exact_navigation_keys(self):
        expected = {
            "PowerPoint / Google Slides": ((0x27,), (0x25,)),
            "Adobe Acrobat / Reader": ((0x11, 0x22), (0x11, 0x21)),
            "SumatraPDF": ((0x22,), (0x21,)),
        }
        self.assertEqual(tuple(expected), win.PROFILES)
        for profile, keys in expected.items():
            for action, expected_keys in zip(("next", "previous"), keys):
                with self.subTest(profile=profile, action=action):
                    self.assertEqual(win.profile_keys(profile, action), expected_keys)

    def test_unknown_profile_or_action_fails_before_native_send(self):
        with self.assertRaises(ValueError):
            win.profile_keys("unrecognized viewer", "next")
        with self.assertRaises(ValueError):
            win.profile_keys(win.PROFILES[0], "up")

    def test_input_uses_real_windows_abi(self):
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            self.assertEqual(ctypes.sizeof(win.MOUSEINPUT), 32)
            self.assertEqual(ctypes.sizeof(win.KEYBDINPUT), 24)
            self.assertEqual(ctypes.sizeof(win.INPUT), 40)
            self.assertEqual(win.INPUT.data.offset, 8)
            self.assertEqual(ctypes.sizeof(win.MSG), 48)
        else:
            self.assertEqual(ctypes.sizeof(win.INPUT), 28)


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        self.controller = win.WindowsController(999, _api=self.api)
        self.addCleanup(self.controller.close)

    def test_arrow_command_is_one_balanced_native_batch(self):
        self.assertTrue(self.controller.send(win.PROFILES[0], "next"))
        self.assertEqual(self.api.sent, [([(0x27, 1), (0x27, 3)], ctypes.sizeof(win.INPUT))])

    def test_control_command_holds_control_until_page_key_released(self):
        self.assertTrue(self.controller.send(win.PROFILES[1], "previous"))
        self.assertEqual(len(self.api.sent), 1)
        self.assertEqual(self.api.sent[0][0], [(0x11, 0), (0x21, 1), (0x21, 3), (0x11, 2)])

    def test_own_process_is_suppressed_including_non_root_window(self):
        self.api.foreground = 8181  # A settings/dialog window, not root_hwnd.
        self.api.foreground_pid = os.getpid()
        self.assertFalse(self.controller.send(win.PROFILES[0], "next"))
        self.assertEqual(self.api.sent, [])
        self.assertIn("Focus", self.controller.last_suppression_reason)

    def test_missing_or_unidentified_foreground_is_suppressed(self):
        for attribute in ("foreground", "foreground_pid"):
            with self.subTest(attribute=attribute):
                original = getattr(self.api, attribute)
                setattr(self.api, attribute, 0)
                self.assertFalse(self.controller.send(win.PROFILES[0], "next"))
                setattr(self.api, attribute, original)
        self.assertEqual(self.api.sent, [])

    def test_held_modifier_suppresses_all_profiles(self):
        for key in (win.VK_CONTROL, win.VK_MENU, win.VK_SHIFT, win.VK_LWIN, win.VK_RWIN):
            for profile in win.PROFILES:
                with self.subTest(key=key, profile=profile):
                    self.api.keys_down = {key}
                    self.assertFalse(self.controller.send(profile, "next"))
                    self.assertIn("Release", self.controller.last_suppression_reason)
        self.assertEqual(self.api.sent, [])

    def test_partial_send_releases_only_injected_unmatched_key_downs(self):
        # Ctrl-down, PgDn-down, PgDn-up arrived; Ctrl-up did not.
        self.api.send_results = [3]
        with self.assertRaisesRegex(win.NavigationError, "3 of 4.*administrator"):
            self.controller.send(win.PROFILES[1], "next")
        self.assertEqual(self.api.sent[1][0], [(win.VK_CONTROL, win.KEYEVENTF_KEYUP)])

    def test_partial_send_releases_chord_in_reverse_order(self):
        self.api.send_results = [2]
        with self.assertRaises(win.NavigationError):
            self.controller.send(win.PROFILES[1], "next")
        self.assertEqual(self.api.sent[1][0], [(win.VK_NEXT, 3), (win.VK_CONTROL, 2)])

    def test_blocked_send_has_permission_guidance_and_no_extra_key_events(self):
        self.api.send_results = [0]
        with self.assertRaisesRegex(win.NavigationError, "same permissions"):
            self.controller.send(win.PROFILES[0], "next")
        self.assertEqual(len(self.api.sent), 1)

    def test_failed_partial_cleanup_explains_how_to_release_keys(self):
        self.api.send_results = [2, 0]
        with self.assertRaisesRegex(win.NavigationError, "Press and release Ctrl"):
            self.controller.send(win.PROFILES[1], "next")

    def test_closed_controller_cannot_send(self):
        self.controller.close()
        self.assertFalse(self.controller.send(win.PROFILES[0], "next"))
        self.assertEqual(self.api.sent, [])


class HotkeyTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        self.controller = win.WindowsController(999, _api=self.api)
        self.addCleanup(self.controller.close)

    def test_registration_uses_global_no_repeat_chords_on_worker(self):
        self.assertEqual(self.controller.register_hotkeys(), [])
        self.assertNotEqual(self.api.registration_thread, threading.get_ident())
        self.assertEqual(
            self.api.registrations,
            [(None, 0x5050, 0x4003, ord("P")), (None, 0x5051, 0x4003, ord("Q"))],
        )
        # Repeated setup must not allocate new shortcuts or threads.
        self.assertEqual(self.controller.register_hotkeys(), [])
        self.assertEqual(len(self.api.registrations), 2)

    def test_conflicting_shortcut_warns_and_only_success_is_unregistered(self):
        self.api.conflicting_keys.add(ord("P"))
        warnings = self.controller.register_hotkeys()
        self.assertEqual(len(warnings), 1)
        self.assertIn("Ctrl+Alt+P", warnings[0])
        self.assertIn("another app", warnings[0])
        self.controller.close()
        self.assertEqual(self.api.unregistrations, [(None, 0x5051, self.api.registration_thread)])

    def test_poll_returns_recognized_hotkeys_then_drains_queue(self):
        self.controller.register_hotkeys()
        self.api.messages.put(0x5050)
        self.api.messages.put(0x2222)  # Not one of our registrations.
        self.api.messages.put(0x5051)
        deadline = time.monotonic() + 1.0
        actions = []
        while len(actions) < 2 and time.monotonic() < deadline:
            actions.extend(self.controller.poll_hotkeys())
            time.sleep(0.005)
        self.assertEqual(actions, ["toggle", "quit"])
        self.assertEqual(self.controller.poll_hotkeys(), [])

    def test_permission_error_is_distinguished_from_shortcut_conflict(self):
        self.api.registration_error = 5
        self.api.conflicting_keys.add(ord("Q"))
        warnings = self.controller.register_hotkeys()
        self.assertEqual(len(warnings), 1)
        self.assertIn("Windows denied permission", warnings[0])
        self.assertNotIn("another app", warnings[0])

    def test_unregister_happens_on_registration_thread_and_close_is_idempotent(self):
        self.controller.register_hotkeys()
        self.controller.close()
        self.controller.close()
        self.assertEqual(len(self.api.unregistrations), 2)
        self.assertTrue(all(item[2] == self.api.registration_thread for item in self.api.unregistrations))
        self.assertFalse(self.controller._hotkey_thread.is_alive())

    def test_close_before_registration_does_not_claim_shortcuts(self):
        self.controller.close()
        self.assertIn("closing", self.controller.register_hotkeys()[0])
        self.assertEqual(self.api.registrations, [])


if __name__ == "__main__":
    unittest.main()
