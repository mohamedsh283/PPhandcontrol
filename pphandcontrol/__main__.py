"""Source entry point and packaged smoke test (never emits navigation keys)."""
import argparse
import json
from pathlib import Path
import sys
import traceback

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pphandcontrol import __version__
from pphandcontrol.paths import model_path, verify_model


def self_test() -> dict:
    import tkinter as tk
    import cv2
    import mediapipe as mp
    import numpy as np
    from PIL import Image, ImageTk
    from pphandcontrol.windows import INPUT
    import ctypes

    verify_model()
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path())),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=2,
    )
    with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
        result = detector.detect_for_video(mp.Image(
            image_format=mp.ImageFormat.SRGB, data=np.zeros((480, 640, 3), dtype=np.uint8)), 1)
        assert not result.hand_landmarks, "Blank image should not contain hands"
    root = tk.Tk()
    root.withdraw()
    try:
        photo = ImageTk.PhotoImage(Image.new("RGB", (16, 16)), master=root)
        root.update()
        assert photo.width() == 16
    finally:
        root.destroy()
    assert ctypes.sizeof(INPUT) == 40, "Expected Windows x64 INPUT layout"
    return {"version": __version__, "result": "passed", "model": "loaded and inferred offline", "tk": "passed", "opencv": cv2.__version__, "camera_opened": False, "navigation_sent": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="PPhandcontrol by Mohamed Sherif")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--self-test", action="store_true", help="Check bundled runtime and model without opening a camera or sending keys")
    parser.add_argument("--report", type=Path, help="Write self-test JSON result to this file")
    args = parser.parse_args()
    try:
        if args.self_test:
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
            result = self_test()
            output = json.dumps(result, indent=2)
            if args.report:
                args.report.write_text(output + "\n", encoding="utf-8")
            if sys.stdout:
                print(output)
            return 0
        if sys.platform != "win32":
            raise RuntimeError("PPhandcontrol supports Windows 10/11 x64.")
        verify_model()
        from pphandcontrol.app import run
        run()
        return 0
    except Exception as exc:
        if args.self_test:
            result = {"version": __version__, "result": "failed", "error": str(exc), "traceback": traceback.format_exc()}
            if args.report:
                try:
                    args.report.parent.mkdir(parents=True, exist_ok=True)
                    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
                except OSError:
                    pass
            if sys.stderr:
                print(result["traceback"], file=sys.stderr)
        else:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("PPhandcontrol could not start", str(exc), parent=root)
            root.destroy()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
