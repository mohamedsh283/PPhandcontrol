"""Tk desktop controls. The camera worker never calls Tk or emits keyboard input."""
from dataclasses import replace
from pathlib import Path
from queue import Empty, Queue
import sys
from time import monotonic
import tkinter as tk
from tkinter import ttk
import webbrowser

from PIL import Image, ImageDraw, ImageTk

from . import __version__
from .camera import TrackingWorker
from .gestures import MODES, create_detector
from .paths import model_path, resource_root
from .session import ControlSession
from .settings import Settings, SettingsStore
from .windows import PROFILES, WindowsController


CONNECTIONS = ((0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7),
               (7, 8), (5, 9), (9, 10), (10, 11), (11, 12), (9, 13),
               (13, 14), (14, 15), (15, 16), (13, 17), (0, 17), (17, 18),
               (18, 19), (19, 20))


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PPhandcontrol · Mohamed Sherif")
        self.root.geometry("1020x760")
        self.root.minsize(880, 700)
        self.root.configure(bg="#f1f5f9")
        self.store = SettingsStore()
        self.settings = self.store.load()
        self.session = ControlSession(create_detector(self.settings.mode, self.settings.sensitivity))
        self.events = Queue(maxsize=1)
        self.worker = None
        self.closed = False
        self.last_draw = 0.0
        self.photo = None
        self.status = tk.StringVar(value="PAUSED · Starting camera…")
        self.tracking = tk.StringVar(value="Thumbs up for Next; thumbs down for Previous.")
        self.last_action = tk.StringVar(value="Last action: none")
        self.notice = tk.StringVar()
        self.shortcut_notice = tk.StringVar()
        self._build_ui()
        self.root.update_idletasks()
        self.controller = WindowsController(self.root.winfo_id())
        self.shortcut_notice.set("\n".join(self.controller.register_hotkeys()))
        self.root.bind("<KeyPress-p>", lambda e: self._shortcut(e, "toggle"))
        self.root.bind("<KeyPress-P>", lambda e: self._shortcut(e, "toggle"))
        self.root.bind("<KeyPress-q>", lambda e: self._shortcut(e, "quit"))
        self.root.bind("<KeyPress-Q>", lambda e: self._shortcut(e, "quit"))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.report_callback_exception = self._callback_error
        self.restart_camera()
        self.root.after(30, self.tick)

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f1f5f9")
        style.configure("TLabel", background="#f1f5f9", foreground="#0f172a", font=("Segoe UI", 10))
        style.configure("Heading.TLabel", font=("Segoe UI Semibold", 22))
        style.configure("Status.TLabel", font=("Segoe UI Semibold", 13), foreground="#0f766e")
        style.configure("Muted.TLabel", foreground="#475569")
        style.configure("Warning.TLabel", foreground="#9a3412")
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 5))
        style.configure("Primary.TButton", background="#0f766e", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#115e59")])
        style.configure("TCheckbutton", background="#f1f5f9", font=("Segoe UI", 10))
        main = ttk.Frame(self.root, padding=22)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="PPhandcontrol", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(main, text="Present with your hands.  By Mohamed Sherif", style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Label(main, text=f"v{__version__}  ·  Video stays on your computer  ·  Free to use; no sale or false authorship", style="Muted.TLabel").pack(side="bottom", anchor="w", pady=(10, 0))
        ttk.Label(main, textvariable=self.shortcut_notice, style="Warning.TLabel", wraplength=950).pack(side="bottom", anchor="w")
        ttk.Label(main, textvariable=self.notice, style="Warning.TLabel", wraplength=950).pack(side="bottom", anchor="w", pady=(8, 0))
        content = ttk.Frame(main)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=0)
        content.rowconfigure(0, weight=1)
        left = ttk.Frame(content)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        self.preview = tk.Canvas(left, bg="#0f172a", height=360, highlightthickness=0)
        self.preview.pack(fill="both", expand=True)
        self.preview.create_text(310, 175, text="Starting your camera…", fill="#cbd5e1", font=("Segoe UI", 14), tags="placeholder")
        ttk.Label(left, text="Thumbs up: NEXT     |     Thumbs down: PREVIOUS", font=("Segoe UI Semibold", 11)).pack(anchor="center", pady=(12, 4))
        self.direction_label = left.winfo_children()[-1]
        ttk.Label(left, textvariable=self.tracking, style="Muted.TLabel", wraplength=590).pack(anchor="w", pady=(4, 0))
        ttk.Label(left, textvariable=self.last_action, font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(8, 0))
        right = ttk.Frame(content, width=260)
        right.grid(row=0, column=1, sticky="ns")
        ttk.Label(right, textvariable=self.status, style="Status.TLabel", wraplength=255).pack(anchor="w", pady=(0, 8))
        self.toggle_button = ttk.Button(right, text="Resume gestures", style="Primary.TButton", command=self.toggle)
        self.toggle_button.pack(fill="x")
        ttk.Label(right, text="P: pause / resume    Q: quit\nGlobal: Ctrl+Alt+P / Ctrl+Alt+Q", style="Muted.TLabel").pack(anchor="w", pady=(8, 10))
        ttk.Label(right, text="Presentation viewer").pack(anchor="w")
        self.profile_var = tk.StringVar(value=self.settings.profile)
        profile = ttk.Combobox(right, textvariable=self.profile_var, values=PROFILES, state="readonly", width=29)
        profile.pack(fill="x", pady=(5, 10))
        profile.bind("<<ComboboxSelected>>", self.change_settings)
        ttk.Label(right, text="Sensitivity").pack(anchor="w")
        self.sensitivity_var = tk.StringVar(value=self.settings.sensitivity)
        sensitivity = ttk.Combobox(right, textvariable=self.sensitivity_var, values=("Low", "Medium", "High"), state="readonly")
        sensitivity.pack(fill="x", pady=(5, 10))
        sensitivity.bind("<<ComboboxSelected>>", self.change_settings)
        ttk.Label(right, text="Gesture mode").pack(anchor="w")
        self.mode_var = tk.StringVar(value=self.settings.mode)
        mode = ttk.Combobox(right, textvariable=self.mode_var, values=MODES, state="readonly")
        mode.pack(fill="x", pady=(5, 10))
        mode.bind("<<ComboboxSelected>>", self.change_settings)
        ttk.Label(right, text="Camera index (usually 0)").pack(anchor="w")
        camera_row = ttk.Frame(right)
        camera_row.pack(fill="x", pady=(5, 4))
        self.camera_var = tk.StringVar(value=str(self.settings.camera))
        ttk.Spinbox(camera_row, from_=0, to=15, textvariable=self.camera_var, width=5).pack(side="left")
        ttk.Button(camera_row, text="Apply camera", command=self.apply_camera).pack(side="right")
        ttk.Button(right, text="Retry camera", command=self.restart_camera).pack(fill="x", pady=(5, 8))
        ttk.Label(right, text="1. Choose mode and viewer.\n2. Resume gestures.\n3. Click the slides or PDF.\n4. Gesture, then relax to repeat.", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Button(right, text="Open quick tutorial", command=self.open_tutorial).pack(fill="x", pady=(0, 6))
        ttk.Button(right, text="Quit", command=self.close).pack(fill="x")
        self._directions()

    def _directions(self) -> None:
        self.direction_label.configure(text=("Thumbs up: NEXT     |     Thumbs down: PREVIOUS" if self.settings.mode == "Thumbs"
                                            else "Point & swipe: LEFT = NEXT     |     RIGHT = PREVIOUS"))

    def _shortcut(self, event, action: str):
        # Modified combinations belong to the global hotkey registration.
        if event.state & 0x000C:
            return None
        if action == "quit":
            self.close()
        else:
            self.toggle()
        return "break"

    def _save(self) -> None:
        try:
            self.store.save(self.settings)
        except OSError as exc:
            self.notice.set(f"Settings work for this session but could not be saved: {exc}")

    def change_settings(self, _event=None) -> None:
        self.session.pause()
        self.settings = replace(self.settings, sensitivity=self.sensitivity_var.get(), mode=self.mode_var.get(), profile=self.profile_var.get())
        self.session.detector = create_detector(self.settings.mode, self.settings.sensitivity)
        self.tracking.set(self.session.detector.status)
        self.notice.set("Settings changed. Gestures are paused; resume when ready.")
        self._save()
        self._directions()
        self._status()

    def apply_camera(self) -> None:
        try:
            camera = int(self.camera_var.get())
            if not 0 <= camera <= 15:
                raise ValueError()
        except ValueError:
            self.notice.set("Enter a camera index from 0 to 15.")
            return
        self.settings = replace(self.settings, camera=camera)
        self._save()
        self.restart_camera()

    def restart_camera(self) -> None:
        self.session.restart_camera()
        if self.worker is not None and not self.worker.stop():
            self.session.camera_error("Windows has not released the camera. Close PPhandcontrol, reconnect your camera, and restart.")
            self._status()
            return
        self.notice.set("Starting camera. Gestures remain paused.")
        self.worker = TrackingWorker(self.settings.camera, self.session.generation, model_path(), self.events)
        self.worker.start()
        self._status()

    def toggle(self) -> None:
        self.session.check_stale()
        if not self.session.toggle():
            self.notice.set(self.session.error or "Wait for a camera image before resuming.")
        else:
            self.notice.set("Gestures paused." if self.session.paused else "Gestures active. Click your presentation window. " + self.session.detector.status)
        self._status()

    def _status(self) -> None:
        if self.session.error:
            self.status.set("PAUSED · Camera error")
            self.notice.set(self.session.error)
        elif not self.session.ready:
            self.status.set("PAUSED · Starting camera…")
        elif self.session.paused:
            self.status.set("PAUSED · Camera ready")
        else:
            self.status.set("ACTIVE · Ready to present")
        self.toggle_button.configure(text="Resume gestures" if self.session.paused else "Pause gestures")

    def draw_frame(self, event) -> None:
        if monotonic() - self.last_draw < 0.045 or not self.root.winfo_viewable():
            return
        self.last_draw = monotonic()
        image = Image.fromarray(event.frame)
        image.thumbnail((max(100, self.preview.winfo_width()), max(100, self.preview.winfo_height())))
        draw = ImageDraw.Draw(image)
        w, h = image.size
        for hand in event.hands:
            points = [(int(p[0] * w), int(p[1] * h)) for p in hand.points]
            for a, b in CONNECTIONS:
                draw.line((points[a], points[b]), fill="#5eead4", width=2)
            for x, y in points:
                draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#fbbf24")
        self.photo = ImageTk.PhotoImage(image, master=self.root)
        self.preview.delete("all")
        self.preview.create_image(self.preview.winfo_width() // 2, self.preview.winfo_height() // 2, image=self.photo)

    def tick(self) -> None:
        if self.closed:
            return
        try:
            for token in self.controller.poll_hotkeys():
                if token == "quit":
                    self.close()
                    return
                if token == "toggle":
                    self.toggle()
            try:
                event = self.events.get_nowait()
            except Empty:
                event = None
            if event is not None and event.generation == self.session.generation:
                action = self.session.process(event)
                if event.frame is not None:
                    self.draw_frame(event)
                if action:
                    try:
                        if self.controller.send(self.settings.profile, action):
                            self.last_action.set(f"Last action: {action.upper()} · {self.settings.profile}")
                        else:
                            self.last_action.set("No command sent · " + self.controller.last_suppression_reason)
                            # A gesture blocked by focus/modifiers was never delivered.
                            # Allow a fresh hold once the viewer can receive input.
                            self.session.detector.reset()
                    except Exception as exc:
                        self.session.pause()
                        self.notice.set(str(exc))
                if self.session.ready:
                    self.tracking.set("Gestures paused; camera preview remains live." if self.session.paused else self.session.detector.status)
            self.session.check_stale()
            self._status()
        except Exception as exc:
            self.session.pause()
            self.notice.set(f"Gestures paused: {exc}")
            self._status()
        finally:
            if not self.closed:
                self.root.after(30, self.tick)

    def open_tutorial(self) -> None:
        roots = ([Path(sys.executable).parent] if getattr(sys, "frozen", False) else []) + [resource_root()]
        for base in roots:
            for relative in ("tutorial/index.html", "tutorial/README.md", "README.md"):
                candidate = base / relative
                if candidate.is_file():
                    webbrowser.open(candidate.resolve().as_uri())
                    return
        self.notice.set("Tutorial missing. Extract the complete ZIP or open the repository README.")

    def _callback_error(self, _kind, value, _traceback) -> None:
        self.session.pause()
        self.notice.set(f"Gestures paused: {value}")
        self._status()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.session.pause()
        self.controller.close()
        if self.worker is not None:
            self.worker.stop()
        self.root.destroy()


def run() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()
