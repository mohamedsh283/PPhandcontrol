"""Validated local preferences; activation is deliberately never persisted."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile
from .gestures import MODES

PROFILES = ("PowerPoint / Google Slides", "Adobe Acrobat / Reader", "SumatraPDF")
SENSITIVITIES = ("Low", "Medium", "High")


@dataclass(frozen=True, slots=True)
class Settings:
    camera: int = 0
    sensitivity: str = "Medium"
    mode: str = "Thumbs"
    profile: str = "PowerPoint / Google Slides"

    def __post_init__(self) -> None:
        if type(self.camera) is not int or not 0 <= self.camera <= 15:
            raise ValueError("Camera must be an integer from 0 through 15")
        if self.sensitivity not in SENSITIVITIES:
            raise ValueError("Unknown sensitivity")
        if self.mode not in MODES:
            raise ValueError("Unknown gesture mode")
        if self.profile not in PROFILES:
            raise ValueError("Unknown navigation profile")


class SettingsStore:
    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        if path is None:
            local_app_data = os.environ.get("LOCALAPPDATA")
            root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
            self.path = root / "PPhandcontrol" / "settings.json"
        else:
            self.path = Path(path)

    def load(self) -> Settings:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return Settings()
            # Unknown keys allow settings written by a newer release to load.
            defaults = asdict(Settings())
            defaults.update({key: value for key, value in data.items() if key in defaults})
            return Settings(**defaults)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            return Settings()

    def save(self, settings: Settings) -> None:
        if not isinstance(settings, Settings):
            raise TypeError("Expected Settings")
        # Revalidate even if a caller bypassed the frozen dataclass guard.
        validated = Settings(**asdict(settings))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix="settings-", suffix=".tmp", delete=False,
            ) as stream:
                temporary_path = stream.name
                json.dump(asdict(validated), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self.path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
