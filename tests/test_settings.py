from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pphandcontrol.settings import PROFILES, Settings, SettingsStore


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "preferences" / "settings.json"
        self.store = SettingsStore(self.path)

    def write_raw(self, text):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding="utf-8")

    def test_missing_file_returns_safe_defaults_without_creating_file(self):
        self.assertEqual(self.store.load(), Settings())
        self.assertFalse(self.path.exists())

    def test_round_trip_preserves_all_preferences(self):
        expected = Settings(camera=2, sensitivity="High", mode="Point & swipe", profile="SumatraPDF")
        self.store.save(expected)
        self.assertEqual(self.store.load(), expected)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), asdict(expected))
        self.assertNotIn("paused", json.loads(self.path.read_text(encoding="utf-8")))

    def test_malformed_or_invalid_data_returns_defaults(self):
        for text in (
            "not json", "[]", "null", '"settings"',
            '{"camera": true}', '{"camera": -1}', '{"camera": 16}',
            '{"camera": 1.5}', '{"camera": "1"}',
            '{"sensitivity": "Extreme"}', '{"mode": "Palm"}',
            '{"profile": "Browser"}', '{"mode": null}',
        ):
            with self.subTest(text=text):
                self.write_raw(text)
                self.assertEqual(self.store.load(), Settings())

    def test_partial_and_unknown_fields_are_supported(self):
        self.write_raw('{"camera": 3, "future_field": "ignored", "paused": false}')
        self.assertEqual(self.store.load(), Settings(camera=3))

    def test_old_swipe_settings_default_to_thumbs_without_reversing(self):
        self.write_raw('{"camera": 2, "reverse": true, "profile": "SumatraPDF"}')
        self.assertEqual(self.store.load(), Settings(camera=2, profile="SumatraPDF", mode="Thumbs"))

    def test_camera_boundaries_match_ui(self):
        for camera in (0, 15):
            with self.subTest(camera=camera):
                self.store.save(Settings(camera=camera))
                self.assertEqual(self.store.load().camera, camera)

    def test_each_navigation_profile_round_trips(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                self.store.save(Settings(profile=profile))
                self.assertEqual(self.store.load().profile, profile)
        self.assertIn("Adobe Acrobat / Reader", PROFILES)

    def test_default_path_uses_local_app_data(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": self.temporary_directory.name}):
            store = SettingsStore()
        self.assertEqual(store.path, Path(self.temporary_directory.name) / "PPhandcontrol" / "settings.json")

    def test_atomic_replace_failure_keeps_previous_file_and_removes_temporary(self):
        self.store.save(Settings(camera=1))
        with patch("pphandcontrol.settings.os.replace", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                self.store.save(Settings(camera=2))
        self.assertEqual(self.store.load(), Settings(camera=1))
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_read_failure_returns_defaults(self):
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            self.assertEqual(self.store.load(), Settings())

    def test_invalid_utf8_returns_defaults(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"\xff\xfe")
        self.assertEqual(self.store.load(), Settings())

    def test_save_requires_settings_instance(self):
        with self.assertRaises(TypeError):
            self.store.save({"camera": 0})


if __name__ == "__main__":
    unittest.main()
