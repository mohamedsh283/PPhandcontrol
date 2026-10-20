"""Small Win32 keyboard boundary; importing this module needs no Windows DLLs.

Hotkeys have their own Windows message queue. Tk must not consume the thread
messages before our application can see them. No keyboard hooks are installed.
"""

from __future__ import annotations

import ctypes
import os
import queue
import sys
import threading
from typing import Literal

PROFILES = (
    "PowerPoint / Google Slides",
    "Adobe Acrobat / Reader",
    "SumatraPDF",
)

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_LWIN = 0x5B
VK_RWIN = 0x5C
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
PM_NOREMOVE = 0
PM_REMOVE = 1

# Fixed-width Windows integers are intentional: c_long is 64-bit on some test
# hosts, but Win32 LONG/DWORD stay 32-bit even in a 64-bit Windows process.
WORD = ctypes.c_uint16
DWORD = ctypes.c_uint32
LONG = ctypes.c_int32
UINT = ctypes.c_uint32
BOOL = ctypes.c_int32
ULONG_PTR = ctypes.c_size_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
HWND = ctypes.c_void_p


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", LONG),
        ("dy", LONG),
        ("mouseData", DWORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", WORD),
        ("wScan", WORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", DWORD), ("wParamL", WORD), ("wParamH", WORD)]


class _INPUTUNION(ctypes.Union):
    # The mouse member is needed even though only keyboard events are sent:
    # it makes sizeof(INPUT) 40 bytes on x64, as required by SendInput.
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", DWORD), ("data", _INPUTUNION)]


class POINT(ctypes.Structure):
    _fields_ = [("x", LONG), ("y", LONG)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", HWND),
        ("message", UINT),
        ("wParam", WPARAM),
        ("lParam", LPARAM),
        ("time", DWORD),
        ("pt", POINT),
        ("lPrivate", DWORD),
    ]


class NavigationError(RuntimeError):
    """Windows could not deliver a complete navigation command."""


def profile_keys(profile: str, action: Literal["next", "previous"]) -> tuple[int, ...]:
    """Return virtual-key codes in press order (release order is reversed)."""
    if action not in ("next", "previous"):
        raise ValueError(f"Unknown navigation action: {action!r}")
    if profile == PROFILES[0]:
        return (VK_RIGHT if action == "next" else VK_LEFT,)
    if profile == PROFILES[1]:
        return (VK_CONTROL, VK_NEXT if action == "next" else VK_PRIOR)
    if profile == PROFILES[2]:
        return (VK_NEXT if action == "next" else VK_PRIOR,)
    raise ValueError(f"Unknown navigation profile: {profile!r}")


class _WinAPI:
    """Bind all signatures explicitly so HWND/pointers are never truncated."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("Presentation keyboard control requires Windows 10 or 11.")
        dll = ctypes.WinDLL("user32", use_last_error=True)
        signatures = {
            "GetForegroundWindow": ([], HWND),
            "GetWindowThreadProcessId": ([HWND, ctypes.POINTER(DWORD)], DWORD),
            "GetAsyncKeyState": ([ctypes.c_int], ctypes.c_int16),
            "SendInput": ([UINT, ctypes.POINTER(INPUT), ctypes.c_int], UINT),
            "RegisterHotKey": ([HWND, ctypes.c_int, UINT, UINT], BOOL),
            "UnregisterHotKey": ([HWND, ctypes.c_int], BOOL),
            "PeekMessageW": ([ctypes.POINTER(MSG), HWND, UINT, UINT, UINT], BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(dll, name)
            function.argtypes = args
            function.restype = result
            setattr(self, name, function)
        self._dll = dll

    @staticmethod
    def last_error() -> int:
        return ctypes.get_last_error()


def _key_input(key: int, *, release: bool = False) -> INPUT:
    event = INPUT()
    event.type = INPUT_KEYBOARD
    event.ki.wVk = key
    # These are the dedicated navigation cluster keys, rather than their
    # numeric-keypad equivalents (which can behave differently with Num Lock).
    extended = KEYEVENTF_EXTENDEDKEY if key in (VK_LEFT, VK_RIGHT, VK_PRIOR, VK_NEXT) else 0
    event.ki.dwFlags = extended | (KEYEVENTF_KEYUP if release else 0)
    return event


class WindowsController:
    """Send to the focused viewer without activating or focusing any window.

    ``send`` belongs on the UI thread. Global shortcuts are registered and
    unregistered on a dedicated message thread; ``poll_hotkeys`` is nonblocking.
    The private API injection keeps native input out of automated tests.
    """

    _HOTKEYS = (
        (0x5050, ord("P"), "toggle", "Ctrl+Alt+P"),
        (0x5051, ord("Q"), "quit", "Ctrl+Alt+Q"),
    )

    def __init__(self, root_hwnd: int, *, _api: object | None = None) -> None:
        self.root_hwnd = root_hwnd
        self._api = _api if _api is not None else _WinAPI()
        self._process_id = os.getpid()
        self._closed = False
        self.last_suppression_reason = ""
        self._events: queue.Queue[str] = queue.Queue()
        self._hotkey_thread: threading.Thread | None = None
        self._hotkey_lock = threading.Lock()
        self._hotkey_ready = threading.Event()
        self._hotkey_stop = threading.Event()
        self._hotkey_warnings: list[str] = []

    def send(self, profile: str, action: Literal["next", "previous"]) -> bool:
        """Send one balanced command; return False if sending is suppressed.

        Any physically held modifier suppresses navigation to avoid turning an
        arrow gesture into an unrelated Alt/Ctrl/Shift/Windows-key shortcut.
        A failed or partial native send raises an actionable NavigationError.
        """
        keys = profile_keys(profile, action)
        self.last_suppression_reason = ""
        if self._closed:
            self.last_suppression_reason = "Keyboard control has closed."
            return False
        foreground = self._api.GetForegroundWindow()
        if not foreground:
            self.last_suppression_reason = "Focus your presentation or PDF viewer."
            return False
        foreground_pid = DWORD()
        thread_id = self._api.GetWindowThreadProcessId(
            foreground, ctypes.byref(foreground_pid)
        )
        if not thread_id or not foreground_pid.value:
            self.last_suppression_reason = "Windows could not identify the focused viewer."
            return False
        if foreground_pid.value == self._process_id:
            self.last_suppression_reason = "Focus your presentation or PDF viewer."
            return False
        if any(
            self._api.GetAsyncKeyState(key) & 0x8000
            for key in (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN)
        ):
            self.last_suppression_reason = "Release Ctrl, Alt, Shift, and Windows keys."
            return False

        events = [*(_key_input(key) for key in keys)]
        events.extend(_key_input(key, release=True) for key in reversed(keys))
        inputs = (INPUT * len(events))(*events)
        sent = int(self._api.SendInput(len(inputs), inputs, ctypes.sizeof(INPUT)))
        if sent != len(inputs):
            error = int(self._api.last_error())
            # Partial insertion can leave one of OUR keys pressed. Only release
            # unmatched key-downs in the inserted prefix, not every profile key.
            pressed: list[int] = []
            for event in events[:max(0, sent)]:
                if event.ki.dwFlags & KEYEVENTF_KEYUP:
                    if event.ki.wVk in pressed:
                        pressed.remove(event.ki.wVk)
                else:
                    pressed.append(event.ki.wVk)
            cleanup_failed = False
            if pressed:
                cleanup = (INPUT * len(pressed))(
                    *(_key_input(key, release=True) for key in reversed(pressed))
                )
                try:
                    cleanup_failed = (
                        self._api.SendInput(len(cleanup), cleanup, ctypes.sizeof(INPUT))
                        != len(cleanup)
                    )
                except OSError:
                    cleanup_failed = True
            details = f" Windows error {error}." if error else ""
            release_guidance = (
                " Press and release Ctrl and the navigation key to clear any held key."
                if cleanup_failed else ""
            )
            raise NavigationError(
                f"Windows delivered {sent} of {len(inputs)} keyboard events.{details} "
                "Focus the viewer and try again. If it runs as administrator, "
                "close it and reopen it normally so both apps use the same permissions."
                + release_guidance
            )
        return True

    def register_hotkeys(self) -> list[str]:
        """Start global Ctrl+Alt+P/Q delivery and report registration conflicts."""
        with self._hotkey_lock:
            if self._closed:
                return ["Global shortcuts are unavailable because the app is closing."]
            if self._hotkey_thread is None:
                self._hotkey_thread = threading.Thread(
                    target=self._hotkey_loop,
                    name="PPhandcontrol shortcuts",
                    daemon=True,
                )
                self._hotkey_thread.start()
        if not self._hotkey_ready.wait(timeout=2.0):
            self._hotkey_stop.set()
            return [
                "Global shortcuts did not start. Use the app's Pause/Resume and Quit buttons."
            ]
        return list(self._hotkey_warnings)

    def _hotkey_loop(self) -> None:
        registered: dict[int, str] = {}
        message = MSG()
        # HWND(-1) selects thread messages only. These belong to this worker,
        # never to Tk's thread, so Tk cannot silently remove WM_HOTKEY messages.
        thread_messages = HWND(-1)
        try:
            self._api.PeekMessageW(
                ctypes.byref(message), thread_messages, WM_HOTKEY, WM_HOTKEY, PM_NOREMOVE
            )
            for identifier, key, token, label in self._HOTKEYS:
                if self._hotkey_stop.is_set():
                    break
                if self._api.RegisterHotKey(
                    None, identifier, MOD_ALT | MOD_CONTROL | MOD_NOREPEAT, key
                ):
                    registered[identifier] = token
                else:
                    error = int(self._api.last_error())
                    if error == 5:
                        reason = "Windows denied permission to register it"
                    elif error == 1409:
                        reason = "another app already uses it"
                    else:
                        reason = f"Windows error {error}; another app may already use it"
                    self._hotkey_warnings.append(
                        f"{label} is unavailable ({reason}). "
                        "Use P/Q while this app is focused, or its buttons."
                    )
            self._hotkey_ready.set()
            while not self._hotkey_stop.is_set():
                for _ in range(32):
                    if not self._api.PeekMessageW(
                        ctypes.byref(message),
                        thread_messages,
                        WM_HOTKEY,
                        WM_HOTKEY,
                        PM_REMOVE,
                    ):
                        break
                    token = registered.get(int(message.wParam))
                    if token is not None:
                        self._events.put(token)
                self._hotkey_stop.wait(0.01)
        except Exception as exc:
            self._hotkey_warnings.append(
                f"Global shortcuts could not start: {exc}. Use the app's buttons."
            )
        finally:
            self._hotkey_ready.set()
            for identifier in registered:
                try:
                    self._api.UnregisterHotKey(None, identifier)
                except OSError:
                    pass

    def poll_hotkeys(self) -> list[str]:
        actions = []
        while True:
            try:
                actions.append(self._events.get_nowait())
            except queue.Empty:
                return actions

    def close(self) -> None:
        """Stop delivery and release registered shortcuts on their owner thread."""
        self._closed = True
        self._hotkey_stop.set()
        thread = self._hotkey_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self.poll_hotkeys()
