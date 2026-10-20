"""Read-only resources, both from source and a portable PyInstaller bundle."""
from pathlib import Path
import sys


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def model_path() -> Path:
    return resource_root() / "models" / "hand_landmarker.task"


def verify_model() -> None:
    import hashlib

    path = model_path()
    expected = path.with_suffix(".task.sha256").read_text(encoding="utf-8").split()[0]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError("The bundled hand model is damaged. Extract a fresh copy of the complete download.")
