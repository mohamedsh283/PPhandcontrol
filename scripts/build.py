"""Test and build the portable Windows x64 distribution without downloading assets."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import time
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
DIST = ROOT / "dist"
APP_NAME = "PPhandcontrol"
ARCHIVE_NAME = f"{APP_NAME}-windows-x64.zip"


def run(*args: str | Path, timeout: int = 900) -> None:
    command = [str(arg) for arg in args]
    print("Running:", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True, timeout=timeout)


def reset_build_directory(path: Path) -> None:
    """Only remove named build artifacts below this checkout's build directory."""
    resolved = path.resolve()
    if resolved == BUILD.resolve() or not resolved.is_relative_to(BUILD.resolve()):
        raise ValueError(f"Refusing to remove a path outside build artifacts: {path}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def verify_model() -> str:
    model = ROOT / "models" / "hand_landmarker.task"
    checksum_file = model.with_suffix(".task.sha256")
    expected = checksum_file.read_text(encoding="utf-8").split()[0].lower()
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        raise ValueError("Invalid committed model checksum")
    with model.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise ValueError(f"Bundled model checksum mismatch: expected {expected}, got {actual}")
    return actual


def copy_licenses(destination: Path) -> list[dict[str, str]]:
    destination.mkdir(parents=True)
    inventory = []
    for distribution in sorted(importlib.metadata.distributions(), key=lambda item: item.metadata["Name"].lower()):
        name = distribution.metadata["Name"]
        inventory.append({"name": name, "version": distribution.version})
        target = destination / f"{name}-{distribution.version}"
        for relative in distribution.files or ():
            if not any(part.lower().startswith(("license", "copying", "notice")) for part in relative.parts):
                continue
            source = Path(distribution.locate_file(relative))
            if not source.is_file():
                continue
            # Retain the package-relative path to avoid colliding LICENSE names.
            safe_parts = [part for part in relative.parts if part not in ("..", ".")]
            output = target.joinpath(*safe_parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
    for source in (ROOT / "packaging" / "licenses").glob("*"):
        if source.is_file():
            shutil.copy2(source, destination / source.name)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.exists():
        python_license = Path(sys.base_prefix) / "LICENSE"
    if not python_license.is_file():
        raise FileNotFoundError("Python runtime LICENSE.txt is required for distribution")
    shutil.copy2(python_license, destination / "PYTHON-LICENSE.txt")
    (destination / "DEPENDENCIES.txt").write_text(
        "Build environment dependency inventory (runtime and build tools)\n\n"
        + "\n".join(f"{item['name']}=={item['version']}" for item in inventory)
        + "\n", encoding="utf-8"
    )
    return inventory


def make_zip(folder: Path, target: Path) -> None:
    # Normalize ordering and timestamps. Freezer/toolchain bytes may still vary.
    epoch = max(int(os.environ.get("SOURCE_DATE_EPOCH", "1767225600")), 315532800)
    timestamp = time.gmtime(epoch)[:6]
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(folder.rglob("*")):
            if source.is_file():
                relative = source.relative_to(folder.parent).as_posix()
                info = zipfile.ZipInfo(relative, timestamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                with source.open("rb") as incoming, archive.open(info, "w", force_zip64=True) as outgoing:
                    shutil.copyfileobj(incoming, outgoing)


def main() -> int:
    if sys.platform != "win32" or struct.calcsize("P") != 8 or sys.version_info[:2] != (3, 12):
        raise SystemExit("Build on Windows with 64-bit CPython 3.12.")
    os.chdir(ROOT)
    BUILD.mkdir(exist_ok=True)
    DIST.mkdir(exist_ok=True)
    model_sha256 = verify_model()
    run(sys.executable, "-m", "pip", "check")
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
    run(sys.executable, "-m", "pphandcontrol", "--self-test", "--report", BUILD / "source-self-test.json")

    frozen = BUILD / "frozen"
    work = BUILD / "pyinstaller"
    specs = BUILD / "specs"
    for folder in (frozen, work, specs):
        reset_build_directory(folder)
    run(
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", APP_NAME, "--paths", ROOT,
        "--distpath", frozen, "--workpath", work, "--specpath", specs,
        "--add-data", f"{ROOT / 'models'}{os.pathsep}models",
        "--collect-all", "mediapipe", "--copy-metadata", "mediapipe",
        "--collect-all", "sounddevice", "--collect-all", "_sounddevice_data",
        "--hidden-import", "PIL._tkinter_finder",
        ROOT / "packaging" / "launcher.py",
    )
    application = frozen / APP_NAME
    executable = application / f"{APP_NAME}.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"Expected executable: {executable}")
    for name in ("README.md", "LICENSE", "CREDITS.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, application / name)
    shutil.copy2(ROOT / "LICENSE", application / "License.txt")
    shutil.copy2(ROOT / "tutorial" / "How to use.txt", application / "How to use.txt")
    shutil.copytree(ROOT / "tutorial", application / "tutorial", dirs_exist_ok=True)
    model_notices = application / "models"
    model_notices.mkdir()
    for source in (ROOT / "models").iterdir():
        if source.is_file() and source.suffix != ".task":
            shutil.copy2(source, model_notices / source.name)
    inventory = copy_licenses(application / "licenses")

    report = application / "self-test.json"
    run(executable, "--self-test", "--report", report, timeout=120)
    if not report.is_file():
        raise RuntimeError("The frozen application did not write its smoke-test report")
    print(report.read_text(encoding="utf-8"), flush=True)
    manifest = {
        "application": APP_NAME,
        "version": tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "architecture": "x64",
        "model_sha256": model_sha256,
        "validation": {
            "unit_tests": "passed",
            "frozen_offline_model_and_tk_smoke_test": "passed",
            "real_camera_swipe_accuracy": "not verified by this build",
            "manual_viewer_and_shortcut_checks": "see tutorial/VALIDATION.md",
        },
        "dependencies": inventory,
    }
    (application / "build-report.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    archive = DIST / ARCHIVE_NAME
    make_zip(application, archive)
    with archive.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    (DIST / "SHA256SUMS.txt").write_text(f"{checksum}  {ARCHIVE_NAME}\n", encoding="ascii")
    shutil.copy2(report, DIST / "self-test.json")
    print(f"Built {archive} ({archive.stat().st_size / 1024 / 1024:.1f} MiB)", flush=True)
    print(f"SHA256: {checksum}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
